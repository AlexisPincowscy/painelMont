"""
Consultas base da camada semântica.

Tudo que toca o banco passa por aqui. Os módulos de tela (grupo, marketing,
empresa, alertas) compõem estas funções — nunca escrevem ORM próprio. É o que
mantém uma definição única por indicador.
"""
from __future__ import annotations

import datetime as dt
import statistics
from decimal import Decimal

from django.db.models import Count, DecimalField, F, Q, Sum, Value
from django.db.models.functions import Coalesce

from core.models import (
    Contrato,
    Empresa,
    Entrega,
    EventoEstagio,
    InvestimentoMarketing,
    Lead,
    MetaPeriodo,
    NaturezaReceita,
    Oportunidade,
    Receita,
)

from .periodo import Periodo, hoje

ESTAGIOS_FUNIL = ["S1", "S2", "S3", "S4", "S5", "S6"]

# Probabilidades iniciais por estágio. São PONTO DE PARTIDA, não verdade:
# `probabilidades(empresa)` as substitui pela conversão observada assim que
# houver amostra suficiente. Chutar é aceitável no dia 1; continuar chutando
# com dado disponível na mesa, não.
PROB_PADRAO = {"S1": 0.02, "S2": 0.05, "S3": 0.10, "S4": 0.20, "S5": 0.45}
AMOSTRA_MINIMA = 30

_D = DecimalField(max_digits=18, decimal_places=2)


def _zero():
    return Coalesce(Sum("valor"), Value(Decimal("0")), output_field=_D)


# ---------------------------------------------------------------- receita
def receita(empresa: Empresa | None, p: Periodo, natureza: str | None = None) -> Decimal:
    """Receita RECONHECIDA. É a única grandeza somável entre empresas."""
    qs = Receita.objects.filter(data_reconhecimento__range=(p.inicio, p.fim))
    if empresa:
        qs = qs.filter(empresa=empresa)
    if natureza:
        qs = qs.filter(natureza=natureza)
    return qs.aggregate(v=_zero())["v"]


def volume_intermediado(empresa: Empresa | None, p: Periodo) -> Decimal:
    """
    VIG — o que passou pela mesa. Exibido em separado e JAMAIS somado à RRG.

    Cada empresa contribui na sua própria grandeza de volume: prêmio
    anualizado, volume estruturado e valor contratado.
    """
    qs = Contrato.objects.filter(data_assinatura__range=(p.inicio, p.fim))
    if empresa:
        qs = qs.filter(empresa=empresa)
    total = Decimal("0")
    for c in qs.only("valor_contratado", "volume_estruturado", "premio_mensal"):
        if c.volume_estruturado:
            total += c.volume_estruturado
        elif c.premio_mensal:
            total += c.premio_mensal * 12
        else:
            total += c.valor_contratado or Decimal("0")
    return total


def meta(empresa: Empresa, p: Periodo) -> Decimal | None:
    m = MetaPeriodo.objects.filter(empresa=empresa, inicio__lte=p.fim, fim__gte=p.inicio).first()
    return m.valor if m else None


# ----------------------------------------------------------------- funil
def probabilidades(empresa: Empresa) -> dict[str, float]:
    """
    Probabilidade de um estágio chegar a S6, calibrada com o histórico real.

    Substitui o palpite por conversão observada sempre que a amostra permite —
    e informa qual foi usada, para que a projeção seja auditável.
    """
    ganhas = set(
        EventoEstagio.objects.filter(empresa=empresa, estagio_canonico="S6")
        .values_list("oportunidade_id", flat=True)
    )
    saida = {}
    for est in ("S1", "S2", "S3", "S4", "S5"):
        alcancaram = set(
            EventoEstagio.objects.filter(empresa=empresa, estagio_canonico=est)
            .values_list("oportunidade_id", flat=True)
        )
        if len(alcancaram) >= AMOSTRA_MINIMA:
            saida[est] = round(len(alcancaram & ganhas) / len(alcancaram), 4)
        else:
            saida[est] = PROB_PADRAO[est]
    return saida


def fator_receita(empresa: Empresa) -> Decimal:
    """
    Quanto de RECEITA cada real de VALOR POTENCIAL do funil gerou historicamente.

    Existe porque `valor_potencial` está na unidade do CONTRATO de cada empresa
    — prêmio anualizado na Montseguro, volume estruturado na Prop5, valor do
    projeto na TechBrabo — e a meta está em RECEITA RECONHECIDA. Comparar
    pipeline com meta sem essa conversão cometeria exatamente o erro que este
    painel existe para evitar: tratar volume intermediado como receita.

    O fator é observado, não arbitrado: sai do próprio histórico da empresa.
    """
    potencial = Oportunidade.objects.filter(empresa=empresa, status="ganha").aggregate(
        v=Coalesce(Sum("valor_potencial"), Value(Decimal("0")), output_field=_D))["v"]
    reconhecido = Receita.objects.filter(empresa=empresa).aggregate(
        v=Coalesce(Sum("valor"), Value(Decimal("0")), output_field=_D))["v"]
    if not potencial:
        return Decimal("1")
    return reconhecido / potencial


def pipeline_ponderado(empresa: Empresa) -> tuple[Decimal, Decimal]:
    """
    Devolve (bruto, ponderado) das oportunidades abertas, JÁ CONVERTIDOS para a
    unidade de receita reconhecida — a mesma da meta.
    """
    probs = probabilidades(empresa)
    fator = fator_receita(empresa)
    bruto = ponderado = Decimal("0")
    for op in Oportunidade.objects.filter(empresa=empresa, status="aberta").only(
            "valor_potencial", "estagio_atual"):
        esperado = op.valor_potencial * fator
        bruto += esperado
        ponderado += esperado * Decimal(str(probs.get(op.estagio_atual, 0.02)))
    return bruto, ponderado


def funil(empresa: Empresa, p: Periodo) -> dict:
    """
    Funil por COORTE: oportunidades criadas no período, contadas em cada estágio
    que já alcançaram alguma vez.

    Contar pelo estágio ATUAL produziria um funil que só mostra onde as coisas
    param, nunca por onde passaram. Contar por evento resolve isso — e é o
    motivo de a tabela de eventos existir.
    """
    coorte = list(
        Oportunidade.objects.filter(empresa=empresa, criada_em__range=(p.inicio, p.fim))
        .values_list("id", flat=True)
    )
    if not coorte:
        return {"etapas": [], "coorte": 0, "maturidade": 0.0}

    alcance = {
        est: EventoEstagio.objects.filter(
            oportunidade_id__in=coorte, estagio_canonico=est
        ).values("oportunidade_id").distinct().count()
        for est in ESTAGIOS_FUNIL
    }
    traducao = {e.estagio_canonico: e.estagio_origem for e in empresa.estagios.all()}

    etapas = []
    for i, est in enumerate(ESTAGIOS_FUNIL):
        est_ant = ESTAGIOS_FUNIL[i - 1] if i else None
        anterior = alcance[est_ant] if est_ant else None
        conversao = (alcance[est] / anterior) if anterior else None
        etapas.append({
            "estagio": est,
            "rotulo": traducao.get(est, est),
            "rotulo_anterior": traducao.get(est_ant, est_ant) if est_ant else None,
            "volume": alcance[est],
            "conversao_da_anterior": round(conversao, 4) if conversao is not None else None,
            "perda": (anterior - alcance[est]) if anterior else 0,
        })

    # Maturidade: fração da coorte que já teve tempo de percorrer o ciclo.
    # Sem isso, a conversão de um mês recente parece uma queda que não existe.
    limite = hoje() - dt.timedelta(days=empresa.ciclo_esperado_dias)
    maduras = Oportunidade.objects.filter(id__in=coorte, criada_em__lte=limite).count()
    return {
        "etapas": etapas,
        "coorte": len(coorte),
        "maturidade": round(maduras / len(coorte), 3),
    }


def gargalo(empresa: Empresa, p: Periodo) -> dict | None:
    """
    A etapa onde mais se perde, traduzida em reais.

    Percentual sozinho não permite priorizar entre empresas com tickets
    diferentes; impacto financeiro permite.
    """
    f = funil(empresa, p)
    if not f["etapas"]:
        return None
    ticket = ticket_medio(empresa, p)
    candidatos = [e for e in f["etapas"] if e["conversao_da_anterior"] is not None]
    if not candidatos:
        return None
    probs = probabilidades(empresa)
    pior, impacto_max = None, Decimal("-1")
    for e in candidatos:
        # Impacto = quantos se perderam × probabilidade de que teriam fechado
        # a partir dali × ticket médio.
        prob = Decimal(str(probs.get(e["estagio"], 0.05)))
        impacto = Decimal(e["perda"]) * prob * ticket
        if impacto > impacto_max:
            pior, impacto_max = e, impacto
    return {**pior, "impacto_estimado": float(impacto_max)}


def ticket_medio(empresa: Empresa, p: Periodo) -> Decimal:
    ag = Contrato.objects.filter(empresa=empresa, data_assinatura__range=(p.inicio, p.fim)).aggregate(
        s=Coalesce(Sum("valor_contratado"), Value(Decimal("0")), output_field=_D), n=Count("id"))
    return (ag["s"] / ag["n"]) if ag["n"] else Decimal("0")


def ciclo_medio(empresa: Empresa, p: Periodo) -> float | None:
    """Mediana de dias entre S1 e S6. Mediana, não média: um negócio atípico de
    ciclo muito longo não deve mover a leitura do time."""
    fechadas = EventoEstagio.objects.filter(
        empresa=empresa, estagio_canonico="S6", data_hora__date__range=(p.inicio, p.fim)
    ).values("oportunidade_id", "data_hora")
    if not fechadas:
        return None
    ids = [f["oportunidade_id"] for f in fechadas]
    entradas = dict(
        EventoEstagio.objects.filter(oportunidade_id__in=ids, estagio_canonico="S1")
        .values_list("oportunidade_id", "data_hora")
    )
    dias = [(f["data_hora"] - entradas[f["oportunidade_id"]]).days
            for f in fechadas if f["oportunidade_id"] in entradas]
    return float(statistics.median(dias)) if dias else None


def conversao_entre(empresa: Empresa, p: Periodo, de: str, para: str) -> float | None:
    f = funil(empresa, p)
    m = {e["estagio"]: e["volume"] for e in f["etapas"]}
    if not m.get(de):
        return None
    return round(m.get(para, 0) / m[de], 4)


# ----------------------------------------------------- realização (S6 → S7)
DEFASAGEM_REALIZACAO = 60  # dias


def taxa_realizacao(empresa: Empresa | None, p: Periodo) -> tuple[float | None, int, int]:
    """
    Contratos que viraram entrega concluída.

    Medida sobre uma janela DEFASADA: contratos assinados ontem ainda não
    tiveram tempo de ser implantados, e incluí-los faria a taxa parecer ruim
    sempre. A defasagem é declarada, não escondida.
    """
    ini = p.inicio - dt.timedelta(days=DEFASAGEM_REALIZACAO)
    fim = p.fim - dt.timedelta(days=DEFASAGEM_REALIZACAO)
    qs = Contrato.objects.filter(data_assinatura__range=(ini, fim))
    if empresa:
        qs = qs.filter(empresa=empresa)
    total = qs.count()
    if not total:
        return None, 0, 0
    concluidos = Entrega.objects.filter(contrato__in=qs, status="concluida").count()
    return round(concluidos / total, 4), concluidos, total


def gap_realizacao(empresa: Empresa | None) -> Decimal:
    """Valor contratado que ainda não virou entrega concluída."""
    qs = Contrato.objects.filter(entrega__status__in=["em_andamento", "atrasada"])
    if empresa:
        qs = qs.filter(empresa=empresa)
    return qs.aggregate(v=Coalesce(Sum("valor_contratado"), Value(Decimal("0")), output_field=_D))["v"]


# ------------------------------------------------------------- marketing
def investimento(empresa: Empresa | None, p: Periodo, canal_id: int | None = None) -> Decimal:
    qs = InvestimentoMarketing.objects.filter(data__range=(p.inicio, p.fim))
    if empresa:
        qs = qs.filter(empresa=empresa)
    if canal_id:
        qs = qs.filter(canal_id=canal_id)
    return qs.aggregate(v=_zero())["v"]


def leads(empresa: Empresa | None, p: Periodo, canal_id: int | None = None) -> int:
    qs = Lead.objects.filter(data_entrada__range=(p.inicio, p.fim))
    if empresa:
        qs = qs.filter(empresa=empresa)
    if canal_id:
        qs = qs.filter(canal_id=canal_id)
    return qs.count()


def novos_clientes(empresa: Empresa | None, p: Periodo, canal_id: int | None = None) -> int:
    qs = Contrato.objects.filter(data_assinatura__range=(p.inicio, p.fim))
    if empresa:
        qs = qs.filter(empresa=empresa)
    if canal_id:
        qs = qs.filter(oportunidade__lead__canal_id=canal_id)
    return qs.count()


def novos_clientes_coorte(empresa: Empresa | None, p: Periodo, canal_id: int | None = None) -> int:
    """
    Clientes cujo LEAD entrou no período — não cujo contrato foi assinado nele.

    Existe porque CPL, CPL qualificado e taxa de aproveitamento são medidos na
    coorte de entrada. Calcular o CAC por data de assinatura misturaria duas
    populações diferentes no mesmo quadro: o numerador viria da verba de agosto
    e o denominador, de leads que entraram em maio. O CAC resultante não erra
    por pouco — ele responde a uma pergunta que ninguém fez.
    """
    qs = Contrato.objects.filter(
        oportunidade__lead__data_entrada__range=(p.inicio, p.fim))
    if empresa:
        qs = qs.filter(empresa=empresa)
    if canal_id:
        qs = qs.filter(oportunidade__lead__canal_id=canal_id)
    return qs.count()


def receita_atribuida(empresa: Empresa | None, p: Periodo, canal_id: int | None = None) -> Decimal:
    """
    Receita ligada à origem do lead — a linhagem id_lead → receita.

    Sem essa chave propagada, CAC e ROAS por canal seriam rateio, e rateio não
    responde à pergunta "onde eu coloco o próximo real?".
    """
    qs = Receita.objects.filter(data_reconhecimento__range=(p.inicio, p.fim))
    if empresa:
        qs = qs.filter(empresa=empresa)
    if canal_id:
        qs = qs.filter(contrato__oportunidade__lead__canal_id=canal_id)
    return qs.aggregate(v=_zero())["v"]


def leads_qualificados(empresa: Empresa | None, p: Periodo, canal_id: int | None = None) -> int:
    """Leads que chegaram a S4 (descoberta) — o lead que interessa."""
    qs = EventoEstagio.objects.filter(
        estagio_canonico="S4",
        oportunidade__lead__data_entrada__range=(p.inicio, p.fim))
    if empresa:
        qs = qs.filter(empresa=empresa)
    if canal_id:
        qs = qs.filter(oportunidade__lead__canal_id=canal_id)
    return qs.values("oportunidade_id").distinct().count()


def roas_coorte(empresa: Empresa | None, p: Periodo, dias: int, canal_id: int | None = None) -> float | None:
    """
    ROAS por COORTE DE ENTRADA DO LEAD.

    Dividir a receita de agosto pelo investimento de agosto é o erro de
    atribuição mais caro do desafio: com o ciclo consultivo da Prop5, a receita
    de agosto veio de leads de maio. Aqui a receita volta para o mês em que o
    lead entrou, e a coorte amadurece em 30, 60 e 90 dias.
    """
    inv = investimento(empresa, p, canal_id)
    if not inv:
        return None
    corte = p.fim + dt.timedelta(days=dias)
    qs = Receita.objects.filter(
        contrato__oportunidade__lead__data_entrada__range=(p.inicio, p.fim),
        data_reconhecimento__lte=min(corte, hoje()))
    if empresa:
        qs = qs.filter(empresa=empresa)
    if canal_id:
        qs = qs.filter(contrato__oportunidade__lead__canal_id=canal_id)
    rec = qs.aggregate(v=_zero())["v"]
    return round(float(rec) / float(inv), 4)


def defasagem_lead_receita(empresa: Empresa | None) -> float | None:
    qs = Receita.objects.select_related("contrato__oportunidade__lead")
    if empresa:
        qs = qs.filter(empresa=empresa)
    dias = []
    vistos = set()
    for r in qs.order_by("data_reconhecimento")[:4000]:
        cid = r.contrato_id
        if cid in vistos:
            continue
        vistos.add(cid)
        entrada = r.contrato.oportunidade.lead.data_entrada
        dias.append((r.data_reconhecimento - entrada).days)
    return float(statistics.median(dias)) if dias else None


def aging_pipeline(empresa: Empresa) -> float | None:
    abertas = Oportunidade.objects.filter(empresa=empresa, status="aberta")
    total = abertas.count()
    if not total:
        return None
    limite = hoje() - dt.timedelta(days=max(7, empresa.ciclo_esperado_dias // 2))
    paradas = abertas.filter(Q(ultima_interacao__lt=limite) | Q(ultima_interacao__isnull=True)).count()
    return round(paradas / total, 4)


def ranking_responsaveis(empresa: Empresa, p: Periodo, limite: int = 8) -> list[dict]:
    dados = []
    for r in empresa.responsaveis.all():
        rec = Receita.objects.filter(
            contrato__oportunidade__responsavel=r,
            data_reconhecimento__range=(p.inicio, p.fim)).aggregate(v=_zero())["v"]
        criadas = Oportunidade.objects.filter(responsavel=r, criada_em__range=(p.inicio, p.fim)).count()
        ganhas = Oportunidade.objects.filter(
            responsavel=r, status="ganha", fechada_em__range=(p.inicio, p.fim)).count()
        dados.append({
            "nome": r.nome, "ativo": r.ativo, "receita": float(rec),
            "oportunidades": criadas, "ganhas": ganhas,
            "conversao": round(ganhas / criadas, 4) if criadas else None,
        })
    return sorted(dados, key=lambda d: d["receita"], reverse=True)[:limite]

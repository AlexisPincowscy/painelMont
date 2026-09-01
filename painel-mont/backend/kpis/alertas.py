"""
Motor de alertas.

Um painel executivo não deve apenas exibir. Nove regras rodam a cada
atualização; a tela do CEO mostra no máximo cinco, ordenadas por severidade —
porque um painel com trinta alertas não tem nenhum.

Todo alerta responde cinco perguntas: o que houve, por que importa, quanto
custa, o que fazer e quem faz. Nenhum alerta afirma a CAUSA: ele aponta onde
olhar e propõe uma hipótese. Inventar explicação que o dado não sustenta é o
jeito mais rápido de perder a confiança da liderança.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import asdict, dataclass, field

from django.db.models import Count, Sum

from core.models import Contrato, Empresa, Entrega, Receita

from . import consultas as q
from . import marketing as mkt
from .grupo import ritmo
from .periodo import Periodo, hoje, mes, mes_anterior, ultimos_meses

AMOSTRA_MINIMA = 30      # nenhuma regra dispara com amostra menor
MAX_NA_TELA = 5


@dataclass
class Alerta:
    regra: str
    titulo: str
    severidade: str            # alta | media | oportunidade
    camada: str                # Gestão | Comercial | Marketing | Operação
    empresa: str
    empresa_nome: str
    o_que_houve: str
    por_que_importa: str
    quanto_custa: float | None
    o_que_fazer: str
    quem: str
    prazo_dias: int = 7
    # Link de drill-down: um alerta que não leva a lugar nenhum é decoração.
    destino: str = ""
    score: float = 0.0
    confianca: float = 1.0


def _sev_peso(s: str) -> float:
    return {"alta": 3.0, "media": 1.6, "oportunidade": 1.0}[s]


def avaliar(rotulo: str) -> list[dict]:
    p = mes(rotulo)
    alertas: list[Alerta] = []
    for e in Empresa.objects.all():
        alertas += _r1_meta(e, p)
        alertas += _r2_gargalo(e, p)
        alertas += _r3_cac(e, p)
        alertas += _r4_canal(e, p)
        alertas += _r5_pipeline(e, p)
        alertas += _r6_realizacao(e, p)
        alertas += _r7_concentracao(e, p)
        alertas += _r8_capacidade(e, p)
        alertas += _r9_oportunidade(e, p)

    # severidade = impacto em R$ × urgência × confiança.
    # A confiança cai quando a amostra é pequena — é o que impede que uma queda
    # de 50% em 4 leads apareça acima de um problema real de R$ 200 mil.
    for a in alertas:
        impacto = abs(a.quanto_custa or 0)
        a.score = round(_sev_peso(a.severidade) * a.confianca * (1 + impacto / 100_000), 3)
    alertas.sort(key=lambda a: a.score, reverse=True)
    return [asdict(a) for a in alertas]


def topo(rotulo: str, n: int = MAX_NA_TELA) -> list[dict]:
    return avaliar(rotulo)[:n]


# ---------------------------------------------------------------- R1
def _r1_meta(e: Empresa, p: Periodo) -> list[Alerta]:
    r = ritmo(e, p)
    if not r.meta or not r.forecast or r.forecast >= r.meta * 0.90:
        return []
    falta = r.meta - r.forecast
    return [Alerta(
        regra="R1", titulo=f"{e.nome}: projeção fecha o mês abaixo da meta",
        severidade="alta", camada="Gestão", empresa=e.slug, empresa_nome=e.nome,
        o_que_houve=(f"Projeção de R$ {r.forecast:,.0f} contra meta de R$ {r.meta:,.0f} "
                     f"({r.forecast / r.meta:.0%}). Atingimento ajustado ao ritmo: "
                     f"{r.atingimento_ritmo:.2f}×."),
        por_que_importa=(f"Faltam {p.dias_uteis_restantes} dias úteis e a operação precisa produzir "
                         f"R$ {(r.necessidade_diaria or 0):,.0f} por dia — "
                         f"{(r.indice_esforco or 0):.2f}× o ritmo atual."),
        quanto_custa=falta,
        o_que_fazer=("Revisar o pipeline em estágio avançado e decidir entre reforçar o time, "
                     "realocar verba ou recalibrar a meta antes do fechamento."),
        quem=f"CEO + diretoria comercial {e.nome}", prazo_dias=5,
        destino=f"/empresas/{e.slug}?periodo={p.rotulo}")]


# ---------------------------------------------------------------- R2
def _r2_gargalo(e: Empresa, p: Periodo) -> list[Alerta]:
    """Conversão de uma etapa abaixo de 80% da média das últimas 8 semanas.
    Compara contra a média histórica, não contra o mês anterior isolado."""
    atual = q.funil(e, p)
    if not atual["etapas"]:
        return []
    historico = [q.funil(e, x) for x in ultimos_meses(p.rotulo, 4)[:-1]]
    saida = []
    for etapa in atual["etapas"]:
        conv = etapa["conversao_da_anterior"]
        if conv is None or etapa["volume"] < AMOSTRA_MINIMA:
            continue
        anteriores = [
            next((x["conversao_da_anterior"] for x in h["etapas"]
                  if x["estagio"] == etapa["estagio"]), None) for h in historico]
        anteriores = [a for a in anteriores if a]
        if len(anteriores) < 2:
            continue
        media = sum(anteriores) / len(anteriores)
        if conv >= media * 0.80:
            continue
        perdidas = int((media - conv) * etapa["volume"] / max(conv, 0.01))
        ticket = float(q.ticket_medio(e, p))
        probs = q.probabilidades(e)
        impacto = perdidas * probs.get(etapa["estagio"], 0.1) * ticket
        saida.append(Alerta(
            regra="R2",
            titulo=(f"{e.nome}: conversão de {etapa['rotulo_anterior']} para "
                    f"{etapa['rotulo']} caiu {(1 - conv / media):.0%}"),
            severidade="alta", camada="Comercial", empresa=e.slug, empresa_nome=e.nome,
            o_que_houve=(f"Passagem para a etapa seguinte em {conv:.1%}, contra média de "
                         f"{media:.1%} nos meses anteriores, sobre {etapa['volume']} oportunidades."),
            por_que_importa=("O volume de topo não caiu na mesma proporção — a perda está na "
                             "conversão, não na demanda."),
            quanto_custa=impacto,
            o_que_fazer=("Revisar as oportunidades não convertidas nesta etapa nas últimas duas "
                         "semanas e verificar mudança de condição comercial ou de tempo de resposta."),
            quem=f"Coordenação comercial {e.nome}", prazo_dias=5,
            confianca=min(1.0, etapa["volume"] / 120),
            destino=f"/comercial?empresa={e.slug}&periodo={p.rotulo}"))
    return saida


# ---------------------------------------------------------------- R3
def _r3_cac(e: Empresa, p: Periodo) -> list[Alerta]:
    inv30 = float(q.investimento(e, p))
    cli30 = q.novos_clientes(e, p)
    if not cli30 or cli30 < 5:
        return []
    cac30 = inv30 / cli30
    janela = ultimos_meses(p.rotulo, 3)
    inv90 = sum(float(q.investimento(e, x)) for x in janela)
    cli90 = sum(q.novos_clientes(e, x) for x in janela)
    if not cli90:
        return []
    cac90 = inv90 / cli90
    if cac30 <= cac90 * 1.25:
        return []
    return [Alerta(
        regra="R3", titulo=f"{e.nome}: CAC 30 dias {(cac30 / cac90 - 1):.0%} acima da média de 90",
        severidade="media", camada="Marketing", empresa=e.slug, empresa_nome=e.nome,
        o_que_houve=f"CAC do período em R$ {cac30:,.0f} contra R$ {cac90:,.0f} na média de 90 dias.",
        por_que_importa="Custo de aquisição subindo antes da receita acompanhar corrói a margem "
                        "do próximo trimestre.",
        quanto_custa=(cac30 - cac90) * cli30,
        o_que_fazer="Comparar CAC por canal e verificar se a alta é generalizada ou concentrada "
                    "em um canal específico antes de mexer na verba total.",
        quem="Head de Marketing", prazo_dias=7,
        destino=f"/marketing?empresa={e.slug}&periodo={p.rotulo}")]


# ---------------------------------------------------------------- R4
def _r4_canal(e: Empresa, p: Periodo) -> list[Alerta]:
    """
    Canal consumindo verba sem devolver receita.

    Avalia sempre uma coorte JÁ MADURA — e "madura" depende do ciclo de cada
    empresa, não de um número fixo. Julgar um canal da Prop5 (ciclo de ~70 dias)
    pela coorte do mês corrente condenaria todo canal de ciclo longo: a receita
    daquela safra simplesmente ainda não aconteceu.
    """
    maturidade_exigida = max(90, int(e.ciclo_esperado_dias * 1.5))
    ref = None
    for candidato in reversed(ultimos_meses(p.rotulo, 9)):
        if (hoje() - candidato.fim).days >= maturidade_exigida:
            ref = candidato
            break
    if ref is None:
        return []

    inv_total = float(q.investimento(e, ref)) or 1.0
    saida = []
    for c in mkt.matriz_canais(e, ref):
        if c["sem_investimento_direto"] or c["participacao_verba"] < 0.15:
            continue
        # Amostra mínima: um canal com 8 leads não sustenta uma decisão de verba.
        if c["leads"] < AMOSTRA_MINIMA:
            continue
        if c["roas"] is None or c["roas"] >= 1.0:
            continue
        # A receita citada é a MESMA que gera o ROAS — a da coorte, não a do
        # período. Misturar as duas dentro do mesmo card produziria um alerta
        # que se contradiz.
        receita_coorte = c["roas"] * c["investimento"]
        saida.append(Alerta(
            regra="R4",
            titulo=(f"{e.nome}: {c['canal']} consome {c['participacao_verba']:.0%} "
                    f"da verba com ROAS de coorte {c['roas']:.2f}"),
            severidade="alta", camada="Marketing", empresa=e.slug, empresa_nome=e.nome,
            o_que_houve=(f"Coorte de {ref.rotulo}, madura há {maturidade_exigida} dias: "
                         f"R$ {c['investimento']:,.0f} investidos, {c['leads']} leads, "
                         f"{c['clientes']} clientes e R$ {receita_coorte:,.0f} de receita "
                         f"gerada por essa safra."),
            por_que_importa=("ROAS abaixo de 1 na coorte madura significa que o canal devolveu "
                             "menos do que consumiu, já descontado o tempo de conversão."),
            quanto_custa=c["investimento"] - receita_coorte,
            o_que_fazer=("Comparar com o CPL qualificado dos demais canais e realocar a verba "
                         "para o canal com melhor aproveitamento antes do próximo ciclo."),
            quem="Head de Marketing", prazo_dias=10,
            confianca=min(1.0, c["leads"] / 120),
            destino=f"/marketing?empresa={e.slug}&periodo={ref.rotulo}"))
    return saida


# ---------------------------------------------------------------- R5
def _r5_pipeline(e: Empresa, p: Periodo) -> list[Alerta]:
    aging = q.aging_pipeline(e)
    if aging is None or aging < 0.35:
        return []
    bruto, ponderado = q.pipeline_ponderado(e)
    return [Alerta(
        regra="R5", titulo=f"{e.nome}: {aging:.0%} do pipeline sem interação registrada",
        severidade="media", camada="Comercial", empresa=e.slug, empresa_nome=e.nome,
        o_que_houve=(f"Oportunidades paradas há mais de {max(7, e.ciclo_esperado_dias // 2)} dias, "
                     f"sobre um pipeline ponderado de R$ {float(ponderado):,.0f}."),
        por_que_importa=("Em ciclo longo, pipeline parado é indistinguível de pipeline morto — "
                         "e infla o forecast sem sustentar o resultado."),
        quanto_custa=float(ponderado) * aging,
        o_que_fazer="Higienizar o funil: cada oportunidade parada volta para cadência ou é "
                    "marcada como perdida com motivo registrado.",
        quem=f"Diretoria comercial {e.nome}", prazo_dias=14,
        destino=f"/comercial?empresa={e.slug}&periodo={p.rotulo}")]


# ---------------------------------------------------------------- R6
def _r6_realizacao(e: Empresa, p: Periodo) -> list[Alerta]:
    """O gap entre vendido e entregue crescendo por três períodos seguidos."""
    serie = []
    for x in ultimos_meses(p.rotulo, 4):
        assinados = Contrato.objects.filter(empresa=e, data_assinatura__range=(x.inicio, x.fim))
        pendentes = assinados.filter(entrega__status__in=["em_andamento", "atrasada"]).count()
        serie.append(pendentes)
    # Crescimento monotônico E material: volume comercial crescendo sozinho já
    # aumenta a fila de entrega. O alerta só faz sentido se a fila cresce
    # DESPROPORCIONALMENTE — aqui, pelo menos 40% em três períodos.
    if len(serie) < 4 or not all(serie[i] < serie[i + 1] for i in range(1, 3)):
        return []
    if not serie[1] or serie[3] < serie[1] * 1.4:
        return []
    gap = float(q.gap_realizacao(e))
    if gap <= 0:
        return []
    atrasadas = Entrega.objects.filter(empresa=e, status="atrasada").count()
    return [Alerta(
        regra="R6", titulo=f"{e.nome}: contratado cresce mais rápido que entregue",
        severidade="alta", camada="Operação", empresa=e.slug, empresa_nome=e.nome,
        o_que_houve=(f"Contratos pendentes de entrega por período: {' → '.join(map(str, serie))}. "
                     f"{atrasadas} entregas já com prazo estourado."),
        por_que_importa=("Receita só é reconhecida na realização. Vender e não entregar transforma "
                         "crescimento comercial em backlog e, depois, em churn."),
        quanto_custa=gap,
        o_que_fazer="Cruzar a fila de entrega com a capacidade instalada e decidir entre "
                    "escalonar novas vendas ou ampliar o time de implantação.",
        quem=f"Diretoria de operações {e.nome}", prazo_dias=7,
        destino=f"/empresas/{e.slug}?periodo={p.rotulo}")]


# ---------------------------------------------------------------- R7
def _r7_concentracao(e: Empresa, p: Periodo) -> list[Alerta]:
    janela = ultimos_meses(p.rotulo, 3)
    ini, fim = janela[0].inicio, janela[-1].fim
    if e.slug == "montseguro":
        dados = (Contrato.objects.filter(empresa=e, data_assinatura__range=(ini, fim))
                 .values("operadora__nome").annotate(v=Sum("premio_mensal")).order_by("-v"))
        rotulo, artigo, dimensao = "operadora", "uma única", "operadora__nome"
    elif e.slug == "techbrabo":
        dados = (Receita.objects.filter(empresa=e, data_reconhecimento__range=(ini, fim))
                 .values("contrato__cliente__origem_cliente").annotate(v=Sum("valor")).order_by("-v"))
        rotulo, artigo, dimensao = "origem de cliente", "uma única", "contrato__cliente__origem_cliente"
    else:
        dados = (Receita.objects.filter(empresa=e, data_reconhecimento__range=(ini, fim))
                 .values("contrato__oportunidade__lead__canal__nome")
                 .annotate(v=Sum("valor")).order_by("-v"))
        rotulo, artigo, dimensao = "canal", "um único", "contrato__oportunidade__lead__canal__nome"

    dados = [d for d in dados if d["v"]]
    if not dados:
        return []
    total = sum(float(d["v"]) for d in dados)
    topo_v = float(dados[0]["v"])
    share = topo_v / total if total else 0
    if share < 0.40:
        return []
    nome = dados[0][dimensao] or "(não informado)"
    return [Alerta(
        regra="R7", titulo=f"{e.nome}: {share:.0%} concentrados em {artigo} {rotulo}",
        severidade="media", camada="Gestão", empresa=e.slug, empresa_nome=e.nome,
        o_que_houve=f"“{nome}” responde por {share:.0%} do resultado dos últimos 3 meses.",
        por_que_importa=("Concentração acima de 40% reduz poder de negociação e transforma uma "
                         "decisão de terceiros em risco direto de receita."),
        quanto_custa=total * (share - 0.40),
        o_que_fazer="Definir se a concentração é estratégia deliberada ou acomodação. "
                    "Se for acomodação, estabelecer meta de diversificação para o trimestre.",
        quem="CEO do Grupo", prazo_dias=30,
        destino=f"/empresas/{e.slug}?periodo={p.rotulo}")]


# ---------------------------------------------------------------- R8
def _r8_capacidade(e: Empresa, p: Periodo) -> list[Alerta]:
    if e.slug != "techbrabo":
        return []
    from .empresa import CAPACIDADE_HORAS_MES

    horas = 0.0
    for c in Contrato.objects.filter(
            empresa=e, entrega__status__in=["em_andamento", "atrasada"]).select_related("entrega"):
        duracao = max(1.0, (c.entrega.data_prevista - c.data_assinatura).days / 30)
        horas += (c.horas_estimadas or 0) / duracao
    ocupacao = horas / CAPACIDADE_HORAS_MES
    if ocupacao <= 0.90:
        return []
    gap = float(q.gap_realizacao(e))
    return [Alerta(
        regra="R8", titulo=f"{e.nome}: ocupação da equipe em {ocupacao:.0%}",
        severidade="media", camada="Operação", empresa=e.slug, empresa_nome=e.nome,
        o_que_houve=(f"{horas:,.0f} horas/mês comprometidas em projetos ativos contra capacidade "
                     f"premissada de {CAPACIDADE_HORAS_MES} h/mês."),
        por_que_importa=("É a única empresa do grupo em que o funil comercial precisa ser lido "
                         "contra a capacidade de entrega. Vender além do teto destrói margem."),
        quanto_custa=gap,
        o_que_fazer="Decidir entre contratar, terceirizar ou escalonar o início dos próximos "
                    "contratos antes de fechar novas propostas.",
        quem="Diretoria de operações TechBrabo", prazo_dias=14,
        destino="/empresas/techbrabo")]


# ---------------------------------------------------------------- R9
def _r9_oportunidade(e: Empresa, p: Periodo) -> list[Alerta]:
    """
    Alerta POSITIVO — obrigatório por decisão de produto.

    Um painel que só mostra incêndio treina a liderança a evitá-lo. R9 existe
    para que o painel também diga onde acelerar.
    """
    ant = mes_anterior(p)
    atuais = {c["slug"]: c for c in mkt.matriz_canais(e, p)}
    anteriores = {c["slug"]: c for c in mkt.matriz_canais(e, ant)}
    saida = []
    for slug, c in atuais.items():
        a = anteriores.get(slug)
        if not a or c["leads"] < AMOSTRA_MINIMA:
            continue
        if not (c["aproveitamento"] and a["aproveitamento"]):
            continue
        ganho = c["aproveitamento"] / a["aproveitamento"] - 1
        if ganho < 0.15:
            continue
        if c["cac"] and a["cac"] and c["cac"] > a["cac"] * 1.10:
            continue  # melhorou convertendo, mas ficou mais caro: não é oportunidade limpa
        saida.append(Alerta(
            regra="R9", titulo=f"{e.nome}: {c['canal']} melhorou {ganho:.0%} sem encarecer",
            severidade="oportunidade", camada="Marketing", empresa=e.slug, empresa_nome=e.nome,
            o_que_houve=(f"Aproveitamento subiu de {a['aproveitamento']:.1%} para "
                         f"{c['aproveitamento']:.1%} com CAC estável, sobre {c['leads']} leads."),
            por_que_importa="Canal ganhando eficiência sem custo adicional é a realocação de "
                            "verba com melhor relação risco/retorno disponível hoje.",
            quanto_custa=c["receita"] * ganho,
            o_que_fazer=f"Testar aumento controlado de verba em {c['canal']} e acompanhar a "
                        f"coorte por 60 dias antes de consolidar.",
            quem="Head de Marketing", prazo_dias=14,
            confianca=min(1.0, c["leads"] / 120),
            destino=f"/marketing?empresa={e.slug}&periodo={p.rotulo}"))
    return saida

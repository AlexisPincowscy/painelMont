"""
Visão individual por empresa.

O briefing é explícito: "não esperamos os mesmos indicadores copiados para as
três operações". Cada função abaixo devolve um conjunto DIFERENTE de KPIs,
porque as três empresas ganham dinheiro de formas diferentes.
"""
from __future__ import annotations

import datetime as dt
import statistics
from collections import defaultdict
from decimal import Decimal

from django.db.models import Count, Sum

from core.models import Contrato, Empresa, Entrega, NaturezaReceita, Receita

from . import consultas as q
from .grupo import ritmo
from .periodo import Periodo, hoje, mes, mes_anterior, ultimos_meses
from .registry import medir

# Capacidade instalada da TechBrabo (horas úteis por mês da equipe de entrega).
# Em produção viria de um cadastro de alocação; aqui é premissa declarada.
CAPACIDADE_HORAS_MES = 3200


def _contratos(empresa: Empresa, p: Periodo):
    return Contrato.objects.filter(empresa=empresa, data_assinatura__range=(p.inicio, p.fim))


# ---------------------------------------------------------------------------
def montseguro(empresa: Empresa, p: Periodo) -> list[dict]:
    """Unidade de valor: a VIDA. Contrato aqui é meio, não fim."""
    ant = mes_anterior(p)

    def vidas(per):
        return Entrega.objects.filter(
            empresa=empresa, status="concluida",
            data_conclusao__range=(per.inicio, per.fim)
        ).aggregate(v=Sum("contrato__num_vidas"))["v"] or 0

    def ape(per):
        pm = _contratos(empresa, per).aggregate(v=Sum("premio_mensal"))["v"] or Decimal("0")
        return float(pm) * 12

    def ticket(per):
        ag = _contratos(empresa, per).aggregate(pm=Sum("premio_mensal"), v=Sum("num_vidas"))
        return float(ag["pm"] or 0) / ag["v"] if ag["v"] else None

    def rec(per, nat):
        return float(q.receita(empresa, per, nat))

    def queda(per):
        cs = _contratos(empresa, per)
        n = cs.count()
        if not n:
            return None
        caidos = sum(1 for c in cs.only("data_assinatura", "data_cancelamento")
                     if c.data_cancelamento and (c.data_cancelamento - c.data_assinatura).days <= 90)
        return caidos / n

    def prazo(per):
        dias = [(e.data_conclusao - e.contrato.data_assinatura).days
                for e in Entrega.objects.filter(empresa=empresa, status="concluida",
                                                data_conclusao__range=(per.inicio, per.fim))
                .select_related("contrato")]
        return float(statistics.median(dias)) if dias else None

    def concentracao(per):
        por_op = (_contratos(empresa, per).values("operadora__nome")
                  .annotate(v=Sum("premio_mensal")).order_by("-v"))
        total = sum(float(x["v"] or 0) for x in por_op)
        return (float(por_op[0]["v"] or 0) / total) if total and por_op else None

    def retencao(per):
        vigentes = Contrato.objects.filter(
            empresa=empresa, data_assinatura__lte=per.fim
        ).exclude(data_cancelamento__lte=per.fim).count()
        base = Contrato.objects.filter(empresa=empresa, data_assinatura__lte=per.fim).count()
        return (vigentes / base) if base else None

    return [
        medir("ms_vidas_implantadas", vidas(p), anterior=vidas(ant),
              tendencia=[vidas(x) for x in ultimos_meses(p.rotulo, 12)],
              detalhe="Implantadas — não contratadas").to_dict(),
        medir("ms_ape", ape(p), anterior=ape(ant)).to_dict(),
        medir("ms_ticket_vida", ticket(p), anterior=ticket(ant)).to_dict(),
        medir("ms_agenciamento", rec(p, NaturezaReceita.AGENCIAMENTO),
              anterior=rec(ant, NaturezaReceita.AGENCIAMENTO)).to_dict(),
        medir("ms_recorrente", rec(p, NaturezaReceita.CORRETAGEM),
              anterior=rec(ant, NaturezaReceita.CORRETAGEM),
              tendencia=[float(q.receita(empresa, x, NaturezaReceita.CORRETAGEM))
                         for x in ultimos_meses(p.rotulo, 12)],
              detalhe="A base estável — cresce sem CAC novo").to_dict(),
        medir("ms_conv_cotacao_proposta", q.conversao_entre(empresa, p, "S4", "S5"),
              anterior=q.conversao_entre(empresa, ant, "S4", "S5")).to_dict(),
        medir("ms_conv_proposta_contrato", q.conversao_entre(empresa, p, "S5", "S6"),
              anterior=q.conversao_entre(empresa, ant, "S5", "S6")).to_dict(),
        medir("ms_prazo_implantacao", prazo(p), anterior=prazo(ant)).to_dict(),
        medir("ms_queda_90d", queda(p), anterior=queda(ant),
              detalhe="Coorte do período; amadurece em 90 dias").to_dict(),
        medir("ms_concentracao_operadora", concentracao(p), anterior=concentracao(ant)).to_dict(),
        medir("ms_retencao", retencao(p), anterior=retencao(ant)).to_dict(),
    ]


# ---------------------------------------------------------------------------
def prop5(empresa: Empresa, p: Periodo) -> list[dict]:
    """Ciclo longo e consultivo. A distinção volume × receita organiza tudo."""
    ant = mes_anterior(p)

    def volume(per):
        return float(_contratos(empresa, per).aggregate(v=Sum("volume_estruturado"))["v"] or 0)

    def comissao(per):
        return float(q.receita(empresa, per, NaturezaReceita.COMISSAO))

    def take(per):
        """
        Take rate sobre os MESMOS contratos.

        Dividir a comissão reconhecida no mês pelo volume estruturado no mês
        compararia populações diferentes: a comissão de agosto vem de operações
        fechadas em junho. Aqui o numerador e o denominador são os contratos
        assinados no período.
        """
        ag = _contratos(empresa, per).aggregate(v=Sum("volume_estruturado"))
        vol = float(ag["v"] or 0)
        if not vol:
            return None
        comissao_contratada = sum(
            float(c.volume_estruturado or 0) * (c.take_rate or 0)
            for c in _contratos(empresa, per).only("volume_estruturado", "take_rate"))
        return comissao_contratada / vol

    def op_cliente(per):
        ag = Contrato.objects.filter(empresa=empresa, data_assinatura__lte=per.fim).aggregate(
            n=Count("id"), c=Count("cliente", distinct=True))
        return (ag["n"] / ag["c"]) if ag["c"] else None

    def reinvestimento(per):
        """Receita de clientes que já tinham contrato anterior — expansão com
        CAC próximo de zero, e a prova de que o Método M5 funciona."""
        total = rein = 0.0
        for r in Receita.objects.filter(
                empresa=empresa, data_reconhecimento__range=(per.inicio, per.fim)
        ).select_related("contrato"):
            total += float(r.valor)
            anteriores = Contrato.objects.filter(
                cliente_id=r.contrato.cliente_id,
                data_assinatura__lt=r.contrato.data_assinatura).exists()
            if anteriores:
                rein += float(r.valor)
        return (rein / total) if total else None

    _, ponderado = q.pipeline_ponderado(empresa)

    return [
        medir("p5_volume_estruturado", volume(p), anterior=volume(ant),
              tendencia=[volume(x) for x in ultimos_meses(p.rotulo, 12)],
              detalhe="VIG — exibido, nunca somado como receita").to_dict(),
        medir("p5_take_rate", take(p), anterior=take(ant)).to_dict(),
        medir("p5_comissao", comissao(p), anterior=comissao(ant),
              tendencia=[float(q.receita(empresa, x, NaturezaReceita.COMISSAO))
                         for x in ultimos_meses(p.rotulo, 12)],
              detalhe="O que entra no consolidado do Grupo").to_dict(),
        medir("p5_lead_diagnostico", q.conversao_entre(empresa, p, "S1", "S4"),
              anterior=q.conversao_entre(empresa, ant, "S1", "S4"),
              detalhe="O portão real de qualificação").to_dict(),
        medir("p5_diagnostico_reuniao", q.conversao_entre(empresa, p, "S4", "S5"),
              anterior=q.conversao_entre(empresa, ant, "S4", "S5")).to_dict(),
        medir("p5_pipeline_ponderado", float(ponderado),
              detalhe="Probabilidade calibrada com histórico real").to_dict(),
        medir("p5_aging", q.aging_pipeline(empresa),
              detalhe="Distingue ciclo longo saudável de pipeline morto").to_dict(),
        medir("p5_ciclo", q.ciclo_medio(empresa, p), anterior=q.ciclo_medio(empresa, ant)).to_dict(),
        medir("p5_operacoes_cliente", op_cliente(p), anterior=op_cliente(ant),
              detalhe="A prova do Método M5").to_dict(),
        medir("p5_reinvestimento", reinvestimento(p), anterior=reinvestimento(ant)).to_dict(),
    ]


# ---------------------------------------------------------------------------
def techbrabo(empresa: Empresa, p: Periodo) -> list[dict]:
    """Onde o comercial encosta na capacidade de entrega."""
    ant = mes_anterior(p)

    def mrr(per):
        return float(q.receita(empresa, per, NaturezaReceita.RECORRENTE))

    def total(per):
        return float(q.receita(empresa, per))

    def mix(per):
        t = total(per)
        return (mrr(per) / t) if t else None

    def backlog():
        contratado = float(Contrato.objects.filter(empresa=empresa).aggregate(
            v=Sum("valor_contratado"))["v"] or 0)
        reconhecido = float(Receita.objects.filter(empresa=empresa).aggregate(
            v=Sum("valor"))["v"] or 0)
        return max(0.0, contratado - reconhecido)

    def margem(per):
        cs = _contratos(empresa, per)
        rec = float(cs.aggregate(v=Sum("valor_contratado"))["v"] or 0)
        custo = float(cs.aggregate(v=Sum("custo_horas"))["v"] or 0)
        return ((rec - custo) / rec) if rec else None

    def ocupacao():
        """
        Horas/mês comprometidas ÷ capacidade instalada.

        As horas de um projeto se distribuem pela sua duração prevista — somar
        o total de horas de todos os projetos ativos contra a capacidade de UM
        mês superestima a ocupação em várias vezes.
        """
        mensal = 0.0
        for c in Contrato.objects.filter(
                empresa=empresa, entrega__status__in=["em_andamento", "atrasada"]
        ).select_related("entrega"):
            duracao = max(1.0, (c.entrega.data_prevista - c.data_assinatura).days / 30)
            mensal += (c.horas_estimadas or 0) / duracao
        return mensal / CAPACIDADE_HORAS_MES

    def lead_time(per):
        dias = [(e.data_conclusao - e.contrato.data_assinatura).days
                for e in Entrega.objects.filter(empresa=empresa, status="concluida",
                                                data_conclusao__range=(per.inicio, per.fim))
                .select_related("contrato")]
        return float(statistics.median(dias)) if dias else None

    def ticket(per):
        ag = _contratos(empresa, per).aggregate(v=Sum("valor_contratado"), n=Count("id"))
        return (float(ag["v"] or 0) / ag["n"]) if ag["n"] else None

    def intercompany(per):
        rs = Receita.objects.filter(empresa=empresa,
                                    data_reconhecimento__range=(per.inicio, per.fim))
        t = float(rs.aggregate(v=Sum("valor"))["v"] or 0)
        g = float(rs.filter(contrato__cliente__origem_cliente="grupo").aggregate(
            v=Sum("valor"))["v"] or 0)
        return (g / t) if t else None

    def nrr(per):
        base = mrr(mes_anterior(per))
        return (mrr(per) / base) if base else None

    risco = Entrega.objects.filter(empresa=empresa, status="atrasada").count()

    return [
        medir("tb_mrr", mrr(p), anterior=mrr(ant),
              tendencia=[float(q.receita(empresa, x, NaturezaReceita.RECORRENTE))
                         for x in ultimos_meses(p.rotulo, 12)],
              detalhe="A base previsível").to_dict(),
        medir("tb_mix_recorrente", mix(p), anterior=mix(ant)).to_dict(),
        medir("tb_nrr", nrr(p), detalhe="Exige 12 meses de histórico para significar algo").to_dict(),
        medir("tb_backlog", backlog(), detalhe="Receita vendida esperando entrega").to_dict(),
        medir("tb_margem_projeto", margem(p), anterior=margem(ant),
              detalhe="Único KPI do grupo que enxerga custo").to_dict(),
        medir("tb_ocupacao", ocupacao(),
              status=("vermelho" if ocupacao() > 0.9 else
                      "amarelo" if ocupacao() > 0.75 or ocupacao() < 0.5 else "verde"),
              detalhe=f"Capacidade premissada: {CAPACIDADE_HORAS_MES} h/mês").to_dict(),
        medir("tb_projetos_risco", risco, detalhe="Entregas com prazo estourado").to_dict(),
        medir("tb_lead_time", lead_time(p), anterior=lead_time(ant)).to_dict(),
        medir("tb_ticket", ticket(p), anterior=ticket(ant)).to_dict(),
        medir("tb_intercompany", intercompany(p), anterior=intercompany(ant),
              detalhe="Leitura de holding: dependência do próprio grupo").to_dict(),
        medir("tb_churn", None, indisponivel_por=(
            "Falta o campo data_cancelamento nos contratos recorrentes da TechBrabo. "
            "Sem ele, MRR cancelado não é distinguível de MRR que apenas parou de ser lançado."
        )).to_dict(),
    ]


CALCULADORAS = {"montseguro": montseguro, "prop5": prop5, "techbrabo": techbrabo}


def tela(slug: str, rotulo: str) -> dict:
    empresa = Empresa.objects.get(slug=slug)
    p = mes(rotulo)
    from dataclasses import asdict

    return {
        "empresa": {"slug": empresa.slug, "nome": empresa.nome, "cor": empresa.cor,
                    "descricao": empresa.descricao, "unidade_valor": empresa.unidade_valor,
                    "ciclo_esperado_dias": empresa.ciclo_esperado_dias,
                    "peso_forecast_ritmo": empresa.peso_forecast_ritmo},
        "periodo": p.rotulo,
        "ritmo": asdict(ritmo(empresa, p)),
        "kpis": CALCULADORAS[slug](empresa, p),
        "funil": q.funil(empresa, p),
        "probabilidades": q.probabilidades(empresa),
    }

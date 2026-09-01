"""
TELA 6 — Saúde dos Dados.

Adição própria à estrutura mínima da seção 4. Existe porque a seção 13 do
briefing trata dado faltante como ACHADO, e um achado que fica num slide não
muda nada: ele precisa virar acompanhamento.

Esta tela mede a completude dos campos críticos, nomeia os KPIs que ficam
bloqueados por cada campo ausente e mostra quem registra bem e quem não
registra. É a única tela do painel voltada para a gestão, não para a liderança
executiva — e é ela que transforma a lista de dados faltantes em melhoria
contínua em vez de queixa.

Princípio: quando um número não pode ser calculado com confiança, o painel diz
isso. Aqui ele diz também POR QUÊ, QUAL CAMPO falta e QUANTO custa em
indicadores perdidos.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import Callable

from django.db.models import Count, Q

from core.models import Contrato, Empresa, EventoEstagio, Lead, Oportunidade

from .periodo import Periodo, hoje, mes
from .registry import REGISTRO

# Completude é métrica de HIGIENE, não de período. Medir no mês daria n=3 para
# a TechBrabo, que fecha poucos contratos grandes — e uma taxa sobre três casos
# é ruído, não diagnóstico. Por isso a janela é móvel e larga, e o tamanho da
# amostra aparece na tela ao lado de cada percentual.
JANELA_DIAS = 180

# Abaixo deste patamar o campo é considerado insuficiente para sustentar os
# indicadores que dependem dele.
LIMIAR_BOM = 0.95
LIMIAR_ATENCAO = 0.75

# Abaixo disso o percentual não é confiável e a tela diz isso em vez de colorir.
AMOSTRA_MINIMA = 20


@dataclass
class Check:
    campo: str
    momento: str
    por_que: str
    kpis: list[str]
    escopo: str  # "todas" ou o slug de uma empresa
    medir: Callable[[Empresa, Periodo], tuple[int, int]]


# ---------------------------------------------------------------- medições
def _m_evento_estagio(e: Empresa, p: Periodo) -> tuple[int, int]:
    """Oportunidades do período que têm pelo menos um evento datado além da
    entrada — sem isso não há ciclo nem gargalo, só fotografia."""
    ops = Oportunidade.objects.filter(empresa=e, criada_em__range=(p.inicio, p.fim))
    total = ops.count()
    com_transicao = (EventoEstagio.objects.filter(oportunidade__in=ops)
                     .exclude(estagio_canonico="S1")
                     .values("oportunidade_id").distinct().count())
    return com_transicao, total


def _m_id_lead(e: Empresa, p: Periodo) -> tuple[int, int]:
    """Contratos rastreáveis até o lead de origem. É a linhagem que sustenta
    CAC e ROAS por canal."""
    cs = Contrato.objects.filter(empresa=e, data_assinatura__range=(p.inicio, p.fim))
    return cs.filter(oportunidade__lead__isnull=False).count(), cs.count()


def _m_motivo_perda(e: Empresa, p: Periodo) -> tuple[int, int]:
    perdidas = Oportunidade.objects.filter(
        empresa=e, status="perdida", fechada_em__range=(p.inicio, p.fim))
    return perdidas.exclude(motivo_perda="").count(), perdidas.count()


def _m_utm(e: Empresa, p: Periodo) -> tuple[int, int]:
    """Leads com campanha identificada. Sem isso a análise para no nível de
    canal e não desce até a peça que gerou o lead."""
    ls = Lead.objects.filter(empresa=e, data_entrada__range=(p.inicio, p.fim))
    return ls.filter(campanha__isnull=False).count(), ls.count()


def _m_interacao(e: Empresa, p: Periodo) -> tuple[int, int]:
    abertas = Oportunidade.objects.filter(empresa=e, status="aberta")
    return abertas.filter(ultima_interacao__isnull=False).count(), abertas.count()


def _m_implantacao(e: Empresa, p: Periodo) -> tuple[int, int]:
    """Contratos com entrega registrada — a ponte S6→S7."""
    cs = Contrato.objects.filter(empresa=e, data_assinatura__range=(p.inicio, p.fim))
    return cs.filter(entrega__isnull=False).count(), cs.count()


def _m_vidas(e: Empresa, p: Periodo) -> tuple[int, int]:
    cs = Contrato.objects.filter(empresa=e, data_assinatura__range=(p.inicio, p.fim))
    return cs.filter(num_vidas__isnull=False, premio_mensal__isnull=False).count(), cs.count()


def _m_take_rate(e: Empresa, p: Periodo) -> tuple[int, int]:
    cs = Contrato.objects.filter(empresa=e, data_assinatura__range=(p.inicio, p.fim))
    return cs.filter(volume_estruturado__isnull=False, take_rate__isnull=False).count(), cs.count()


def _m_horas(e: Empresa, p: Periodo) -> tuple[int, int]:
    cs = Contrato.objects.filter(empresa=e, data_assinatura__range=(p.inicio, p.fim))
    return cs.filter(horas_estimadas__isnull=False, custo_horas__isnull=False).count(), cs.count()


def _m_cancelamento(e: Empresa, p: Periodo) -> tuple[int, int]:
    """
    Caso especial e o mais honesto da tela.

    `data_cancelamento` só existe na Montseguro. Nas outras duas o campo não
    foi modelado — e por isso `tb_churn` aparece indisponível na tela da
    TechBrabo. Medir "0 de 0" seria esconder o problema; devolver (0, -1)
    marca o campo como INEXISTENTE, que é diferente de vazio.
    """
    # Verificação ESTRUTURAL, não de preenchimento: o campo é opcional por
    # natureza (só contratos cancelados o têm), então uma taxa de preenchimento
    # não significaria nada. O que importa é se ele EXISTE no modelo — e ele só
    # existe na Montseguro. É por isso que `tb_churn` aparece indisponível.
    return (0, -2) if e.slug == "montseguro" else (0, -1)


CHECKS: list[Check] = [
    Check("data_hora_mudanca_estagio", "Toda transição de estágio",
          "Sem evento datado não existe ciclo médio nem análise de gargalo — só fotografia.",
          ["ciclo_medio", "conv_s1_s6", "p5_ciclo", "tb_lead_time"], "todas", _m_evento_estagio),
    Check("id_lead_origem", "Propagado do lead até o contrato",
          "É a linhagem que sustenta o painel de marketing inteiro. Sem ela, sobra rateio — "
          "e rateio não responde onde investir.",
          ["cac", "roas", "roas_coorte", "cpl_qualificado"], "todas", _m_id_lead),
    Check("motivo_perda", "Ao marcar a oportunidade como perdida",
          "É o 'porquê' do vazamento. O funil mostra onde se perde; só este campo mostra por quê.",
          ["conv_s1_s6"], "todas", _m_motivo_perda),
    Check("campanha / UTM", "Na entrada do lead",
          "Sem campanha identificada, a análise para no nível de canal e não desce até a peça.",
          ["participacao_verba", "cpl"], "todas", _m_utm),
    Check("ultima_interacao", "A cada contato com a oportunidade",
          "É o que distingue ciclo longo saudável de pipeline morto.",
          ["p5_aging"], "todas", _m_interacao),
    Check("data_implantacao_concluida", "Na ativação da vigência / go-live",
          "A ponte S6→S7. Vender e não realizar é o vazamento mais caro e mais invisível.",
          ["taxa_realizacao", "ms_prazo_implantacao", "tb_lead_time"], "todas", _m_implantacao),
    Check("num_vidas + premio_per_capita", "Na cotação e na contratação",
          "A unidade real do negócio. Sem eles, um contrato de 3 vidas conta igual a um de 180.",
          ["ms_vidas_implantadas", "ms_ticket_vida", "ms_ape"], "montseguro", _m_vidas),
    Check("volume_estruturado + take_rate", "No fechamento da operação",
          "É o que separa volume intermediado de receita — a distinção central do painel.",
          ["p5_take_rate", "p5_volume_estruturado"], "prop5", _m_take_rate),
    Check("horas_e_custo_por_projeto", "Apontamento semanal",
          "Único dado de custo do grupo. Sem ele o painel mede receita, nunca margem.",
          ["tb_margem_projeto", "tb_ocupacao"], "techbrabo", _m_horas),
    Check("data_cancelamento + motivo", "Na saída do cliente",
          "Churn, queda em 90 dias e retenção dependem dele. Não existe fora da Montseguro.",
          ["ms_queda_90d", "ms_retencao", "tb_churn"], "todas", _m_cancelamento),
]


def janela(p: Periodo) -> Periodo:
    """Janela móvel de 180 dias terminando no fim do período selecionado."""
    fim = min(p.fim, hoje())
    return Periodo(fim - dt.timedelta(days=JANELA_DIAS), fim, f"{JANELA_DIAS}d")


def _status(taxa: float | None) -> str:
    if taxa is None:
        return "cinza"
    if taxa >= LIMIAR_BOM:
        return "verde"
    if taxa >= LIMIAR_ATENCAO:
        return "amarelo"
    return "vermelho"


def _nome_kpi(slug: str) -> str:
    k = REGISTRO.get(slug)
    return k.nome if k else slug


def completude(p: Periodo) -> list[dict]:
    """Uma linha por campo crítico, com a taxa de preenchimento por empresa."""
    p = janela(p)
    empresas = list(Empresa.objects.all())
    linhas = []
    for c in CHECKS:
        por_empresa = []
        for e in empresas:
            if c.escopo not in ("todas", e.slug):
                por_empresa.append({"empresa": e.slug, "nome": e.nome, "cor": e.cor,
                                    "aplicavel": False, "taxa": None, "status": "cinza",
                                    "preenchidos": 0, "total": 0})
                continue
            preenchidos, total = c.medir(e, p)
            if total in (-1, -2):
                # Verificação ESTRUTURAL: o que se reporta é a existência do
                # campo no modelo, não uma taxa. Exibir "100% de 1" daria a
                # impressão de uma medição que não foi feita.
                existe = total == -2
                por_empresa.append({"empresa": e.slug, "nome": e.nome, "cor": e.cor,
                                    "aplicavel": True, "taxa": None,
                                    "status": "verde" if existe else "vermelho",
                                    "preenchidos": 0, "total": 0,
                                    "estrutural": True, "inexistente": not existe})
                continue
            taxa = (preenchidos / total) if total else None
            # Amostra pequena: mostra o número, mas não pinta o semáforo. Colorir
            # uma taxa sobre cinco casos daria autoridade a um dado que não a tem.
            confiavel = total >= AMOSTRA_MINIMA
            por_empresa.append({"empresa": e.slug, "nome": e.nome, "cor": e.cor,
                                "aplicavel": True, "taxa": taxa,
                                "status": _status(taxa) if confiavel else "cinza",
                                "amostra_pequena": not confiavel,
                                "preenchidos": preenchidos, "total": total})
        piores = [x["taxa"] for x in por_empresa if x.get("taxa") is not None]
        linhas.append({
            "campo": c.campo, "momento": c.momento, "por_que": c.por_que,
            "escopo": c.escopo,
            "kpis_dependentes": [{"slug": s, "nome": _nome_kpi(s)} for s in c.kpis],
            "por_empresa": por_empresa,
            "pior_taxa": min(piores) if piores else None,
            "critico": any(x.get("inexistente") or
                           (x.get("taxa") is not None and not x.get("amostra_pequena")
                            and x["taxa"] < LIMIAR_ATENCAO)
                           for x in por_empresa),
        })
    # Pior primeiro: a tela é uma fila de trabalho, não um relatório.
    return sorted(linhas, key=lambda l: (not l["critico"], l["pior_taxa"] if l["pior_taxa"] is not None else 1))


def kpis_bloqueados() -> list[dict]:
    """
    KPIs que o painel declara como não calculáveis.

    Hoje sai da própria camada semântica: qualquer indicador entregue com
    `indisponivel_por` preenchido aparece aqui, com o motivo que o front já
    mostra em cinza na tela da empresa. A lista não é mantida à mão.
    """
    from . import empresa as empresa_mod

    bloqueados = []
    for e in Empresa.objects.all():
        for m in empresa_mod.CALCULADORAS[e.slug](e, mes("2026-08")):
            if m["indisponivel_por"]:
                bloqueados.append({"empresa": e.nome, "cor": e.cor, "kpi": m["nome"],
                                   "slug": m["slug"], "motivo": m["indisponivel_por"]})
    return bloqueados


def registro_por_responsavel(p: Periodo) -> list[dict]:
    """
    Quem registra bem e quem não registra.

    Completude de dado não é problema de sistema, é problema de rotina. Sem
    nome, ninguém corrige; com nome, vira acompanhamento de gestão — e por isso
    esta tela fica fora do menu executivo.
    """
    p = janela(p)
    linhas = []
    for e in Empresa.objects.all():
        for r in e.responsaveis.all():
            perdidas = Oportunidade.objects.filter(
                responsavel=r, status="perdida", fechada_em__range=(p.inicio, p.fim))
            abertas = Oportunidade.objects.filter(responsavel=r, status="aberta")
            n_perdidas, n_abertas = perdidas.count(), abertas.count()
            if not (n_perdidas or n_abertas):
                continue
            com_motivo = perdidas.exclude(motivo_perda="").count()
            com_interacao = abertas.filter(ultima_interacao__isnull=False).count()
            taxas = []
            if n_perdidas:
                taxas.append(com_motivo / n_perdidas)
            if n_abertas:
                taxas.append(com_interacao / n_abertas)
            geral = sum(taxas) / len(taxas)
            linhas.append({
                "responsavel": r.nome, "ativo": r.ativo,
                "empresa": e.nome, "cor": e.cor,
                "motivo_perda": (com_motivo / n_perdidas) if n_perdidas else None,
                "interacao": (com_interacao / n_abertas) if n_abertas else None,
                "geral": geral, "status": _status(geral),
                "oportunidades": n_perdidas + n_abertas,
            })
    return sorted(linhas, key=lambda x: x["geral"])


def tela(rotulo: str) -> dict:
    p = mes(rotulo)
    linhas = completude(p)
    bloqueados = kpis_bloqueados()
    taxas = [l["pior_taxa"] for l in linhas if l["pior_taxa"] is not None]
    indice = sum(taxas) / len(taxas) if taxas else None
    j = janela(p)
    return {
        "periodo": p.rotulo,
        "janela": {"dias": JANELA_DIAS, "inicio": j.inicio.isoformat(), "fim": j.fim.isoformat()},
        "amostra_minima": AMOSTRA_MINIMA,
        "indice_geral": indice,
        "status_geral": _status(indice),
        "campos_criticos": sum(1 for l in linhas if l["critico"]),
        "kpis_bloqueados": bloqueados,
        "completude": linhas,
        "responsaveis": registro_por_responsavel(p),
        "limiares": {"bom": LIMIAR_BOM, "atencao": LIMIAR_ATENCAO},
    }

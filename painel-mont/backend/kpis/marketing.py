"""
Tela de Marketing: ligar investimento a RECEITA, não a volume.

O painel existe para responder uma pergunta só — onde colocar o próximo real.
"""
from __future__ import annotations

from core.models import Canal, Empresa

from . import consultas as q
from .periodo import mes, mes_anterior, ultimos_meses
from .registry import medir


def cascata(empresa: Empresa | None, p) -> list[dict]:
    """
    Investimento → leads → qualificados → oportunidades → vendas → receita.

    A taxa de passagem entre cada par é o que mostra onde a verba vira (ou
    deixa de virar) resultado.
    """
    lds = q.leads(empresa, p)
    qual = q.leads_qualificados(empresa, p)
    # Coorte, não data de assinatura: a cascata inteira acompanha a MESMA
    # população de leads da entrada até a receita.
    vendas = q.novos_clientes_coorte(empresa, p)
    etapas = [
        {"rotulo": "Investimento", "valor": float(q.investimento(empresa, p)), "unidade": "BRL"},
        {"rotulo": "Leads", "valor": lds, "unidade": "UN"},
        {"rotulo": "Qualificados (S4)", "valor": qual, "unidade": "UN"},
        {"rotulo": "Vendas", "valor": vendas, "unidade": "UN"},
        {"rotulo": "Receita reconhecida", "valor": float(q.receita_atribuida(empresa, p)),
         "unidade": "BRL"},
    ]
    for i, e in enumerate(etapas):
        anterior = etapas[i - 1]["valor"] if i else None
        e["passagem"] = (
            round(e["valor"] / anterior, 4)
            if (i and anterior and e["unidade"] == etapas[i - 1]["unidade"] == "UN")
            else None
        )
    return etapas


def matriz_canais(empresa: Empresa | None, p) -> list[dict]:
    """
    Um canal que gera muitos leads não é necessariamente eficiente.

    Volume × CAC × ROAS em uma linha por canal — os três eixos que decidem
    realocação de verba.

    Dois ROAS diferentes, de propósito:

      roas_caixa   — receita reconhecida no período ÷ investimento do período.
                     É o que a maioria dos painéis chama de ROAS. Infla, porque
                     mistura receita recorrente de safras antigas com verba nova.

      roas_coorte  — receita gerada pelos leads QUE ENTRARAM no período, medida
                     até 90 dias depois. É a métrica de decisão: só ela compara
                     canais respeitando o ciclo de cada negócio.

    A coorte do mês corrente ainda não maturou; `coorte_madura` diz isso em vez
    de deixar o número parecer um desempenho ruim.
    """
    from .periodo import hoje
    import datetime as _dt

    linhas = []
    madura = (hoje() - p.fim).days >= 90
    total_inv = float(q.investimento(empresa, p)) or 1.0
    for canal in Canal.objects.all():
        inv = float(q.investimento(empresa, p, canal.id))
        lds = q.leads(empresa, p, canal.id)
        if not inv and not lds:
            continue
        qual = q.leads_qualificados(empresa, p, canal.id)
        clientes = q.novos_clientes_coorte(empresa, p, canal.id)
        rec = float(q.receita_atribuida(empresa, p, canal.id))
        linhas.append({
            "canal": canal.nome, "slug": canal.slug, "pago": canal.pago,
            "investimento": inv, "leads": lds, "qualificados": qual,
            "clientes": clientes, "receita": rec,
            "cpl": (inv / lds) if (inv and lds) else None,
            "cpl_qualificado": (inv / qual) if (inv and qual) else None,
            "aproveitamento": (qual / lds) if lds else None,
            "cac": (inv / clientes) if (inv and clientes) else None,
            "roas_caixa": (rec / inv) if inv else None,
            "roas": q.roas_coorte(empresa, p, 90, canal.id),
            "coorte_madura": madura,
            "participacao_verba": inv / total_inv,
            # Canais orgânicos e de indicação não têm investimento direto. Em vez
            # de ratear (o que seria inventar dado), o painel diz isso.
            "sem_investimento_direto": inv == 0,
        })
    return sorted(linhas, key=lambda x: x["receita"], reverse=True)


def maturacao_coortes(empresa: Empresa | None, rotulo: str, n: int = 6) -> list[dict]:
    """
    ROAS por coorte de ENTRADA DO LEAD, em 30/60/90 dias.

    É a correção do erro de atribuição mais caro do desafio. A coorte do mês
    corrente sempre parece ruim — isso é imaturidade, não ineficiência, e o
    front rotula assim.
    """
    saida = []
    for p in ultimos_meses(rotulo, n):
        saida.append({
            "coorte": p.rotulo,
            "investimento": float(q.investimento(empresa, p)),
            "leads": q.leads(empresa, p),
            "roas_30": q.roas_coorte(empresa, p, 30),
            "roas_60": q.roas_coorte(empresa, p, 60),
            "roas_90": q.roas_coorte(empresa, p, 90),
        })
    return saida


def tela(rotulo: str, empresa_slug: str | None = None) -> dict:
    p = mes(rotulo)
    ant = mes_anterior(p)
    empresa = Empresa.objects.filter(slug=empresa_slug).first() if empresa_slug else None

    def _kpi(slug, fn):
        return medir(slug, fn(p), anterior=fn(ant)).to_dict()

    inv = float(q.investimento(empresa, p))
    lds = q.leads(empresa, p)
    qual = q.leads_qualificados(empresa, p)
    clientes = q.novos_clientes_coorte(empresa, p)
    rec = float(q.receita_atribuida(empresa, p))

    inv_a = float(q.investimento(empresa, ant))
    lds_a = q.leads(empresa, ant)
    qual_a = q.leads_qualificados(empresa, ant)
    cli_a = q.novos_clientes_coorte(empresa, ant)
    rec_a = float(q.receita_atribuida(empresa, ant))

    return {
        "periodo": p.rotulo,
        "empresa": empresa.slug if empresa else None,
        "kpis": [
            medir("investimento", inv, anterior=inv_a,
                  tendencia=[float(q.investimento(empresa, x)) for x in ultimos_meses(rotulo, 12)]).to_dict(),
            medir("cpl", (inv / lds) if lds else None,
                  anterior=(inv_a / lds_a) if lds_a else None).to_dict(),
            medir("cpl_qualificado", (inv / qual) if qual else None,
                  anterior=(inv_a / qual_a) if qual_a else None).to_dict(),
            medir("aproveitamento", (qual / lds) if lds else None,
                  anterior=(qual_a / lds_a) if lds_a else None,
                  detalhe=f"{qual} de {lds} leads chegaram a S4").to_dict(),
            medir("cac", (inv / clientes) if clientes else None,
                  anterior=(inv_a / cli_a) if cli_a else None,
                  detalhe=f"{clientes} novos clientes").to_dict(),
            medir("roas", q.roas_coorte(empresa, p, 90),
                  anterior=q.roas_coorte(empresa, ant, 90),
                  detalhe="Coorte de entrada do lead, medida em 90 dias").to_dict(),
            medir("defasagem_receita", q.defasagem_lead_receita(empresa),
                  detalhe="Define a janela honesta para julgar um canal").to_dict(),
        ],
        "cascata": cascata(empresa, p),
        "canais": matriz_canais(empresa, p),
        "coortes": maturacao_coortes(empresa, rotulo),
    }

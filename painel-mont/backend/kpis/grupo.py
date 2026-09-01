"""
Camada de grupo: ritmo, forecast, semáforo e comparação entre empresas.

Aqui vive a resposta à pergunta central do briefing — onde agir, investir,
corrigir ou acelerar.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from decimal import Decimal

from core.models import Empresa

from . import consultas as q
from .periodo import Periodo, mes, mes_anterior, ultimos_meses
from .registry import medir


@dataclass
class Ritmo:
    """
    O bloco que substitui "62% da meta" por uma leitura acionável.

    Percentual de meta no dia 20 pode ser excelente ou catastrófico. O que a
    liderança precisa é: onde deveríamos estar, quanto falta por dia, e quanto
    de esforço extra isso representa.
    """

    meta: float | None
    realizado: float
    meta_esperada_hoje: float | None
    gap: float | None
    atingimento_ritmo: float | None
    forecast: float | None
    necessidade_diaria: float | None
    indice_esforco: float | None
    cobertura_pipeline: float | None
    pipeline_bruto: float
    pipeline_ponderado: float
    dias_uteis_decorridos: int
    dias_uteis_totais: int
    peso_ritmo: float
    status: str


def _status(atingimento, esforco, cobertura, tem_meta: bool) -> str:
    """
    Semáforo com REGRA, não com sensação.

    Três condições combinadas de propósito: uma empresa pode estar em 98% da
    meta e ainda assim ser vermelha, se a cobertura de pipeline caiu para 0,8× —
    o mês fecha bem e o próximo não. Semáforo só de atingimento é retrovisor;
    combinado com cobertura, vira para-brisa.
    """
    if not tem_meta or atingimento is None:
        return "cinza"
    # A cobertura só entra na regra quando o gap ainda é material. Quando falta
    # pouco para a meta, ela fica numericamente instável (denominador quase
    # zero) e pintaria de vermelho justamente quem está prestes a bater — o
    # oposto do que o indicador quer dizer.
    if atingimento < 0.85 or (esforco is not None and esforco > 1.30) or \
       (cobertura is not None and cobertura < 1.5):
        return "vermelho"
    if atingimento < 0.95 or (esforco is not None and esforco > 1.10) or \
       (cobertura is not None and cobertura < 3.0):
        return "amarelo"
    return "verde"


def ritmo(empresa: Empresa, p: Periodo) -> Ritmo:
    realizado = float(q.receita(empresa, p))
    alvo = q.meta(empresa, p)
    bruto, ponderado = q.pipeline_ponderado(empresa)
    fracao = p.fracao_decorrida or 1.0

    if alvo is None:
        return Ritmo(None, realizado, None, None, None, None, None, None, None,
                     float(bruto), float(ponderado), p.dias_uteis_decorridos,
                     p.dias_uteis_totais, empresa.peso_forecast_ritmo, "cinza")

    alvo_f = float(alvo)
    esperado = alvo_f * fracao
    gap = realizado - esperado
    atingimento = realizado / esperado if esperado else None

    # Forecast híbrido: ritmo observado + funil, ponderados pelo tipo de ciclo.
    # w alto em negócio transacional (ritmo confiável); w baixo em ciclo longo
    # com poucos fechamentos grandes (ritmo ruidoso, o funil prevê melhor).
    f_ritmo = realizado / fracao if fracao else realizado
    f_pipeline = realizado + float(ponderado) * (p.dias_uteis_restantes / max(p.dias_uteis_totais, 1))
    w = empresa.peso_forecast_ritmo
    forecast = w * f_ritmo + (1 - w) * f_pipeline

    restante = max(0.0, alvo_f - realizado)
    dias_rest = p.dias_uteis_restantes
    necessidade = restante / dias_rest if dias_rest else None
    media_diaria = realizado / p.dias_uteis_decorridos if p.dias_uteis_decorridos else None
    esforco = (necessidade / media_diaria) if (necessidade and media_diaria) else None
    # Gap residual (< 10% da meta): a cobertura vira informativa, não decisória.
    gap_material = restante > alvo_f * 0.10
    cobertura = (float(ponderado) / restante) if restante > 0 else None
    cobertura_para_status = cobertura if gap_material else None

    return Ritmo(
        meta=alvo_f, realizado=realizado, meta_esperada_hoje=esperado, gap=gap,
        atingimento_ritmo=atingimento, forecast=forecast,
        necessidade_diaria=necessidade, indice_esforco=esforco,
        cobertura_pipeline=cobertura, pipeline_bruto=float(bruto),
        pipeline_ponderado=float(ponderado),
        dias_uteis_decorridos=p.dias_uteis_decorridos,
        dias_uteis_totais=p.dias_uteis_totais, peso_ritmo=w,
        status=_status(atingimento, esforco, cobertura_para_status, True))


def cartao_empresa(empresa: Empresa, p: Periodo) -> dict:
    """O card de semáforo da tela do CEO — a informação dos primeiros 5 segundos."""
    r = ritmo(empresa, p)
    anterior = float(q.receita(empresa, mes_anterior(p)))
    serie = [float(q.receita(empresa, x)) for x in ultimos_meses(p.rotulo, 12)]
    return {
        "empresa": {"slug": empresa.slug, "nome": empresa.nome, "cor": empresa.cor,
                    "unidade_valor": empresa.unidade_valor, "descricao": empresa.descricao},
        "ritmo": asdict(r),
        "receita": medir("rrg", r.realizado, anterior=anterior, meta=r.meta,
                         tendencia=serie).to_dict(),
        "vig": medir("vig", float(q.volume_intermediado(empresa, p)),
                     detalhe="Não somado à RRG").to_dict(),
    }


def comparacao(p: Periodo) -> list[dict]:
    """
    Comparação NORMALIZADA entre empresas.

    Só entram grandezas em razão, percentual ou tempo. Receita absoluta,
    ticket médio e volume ficam de fora: uma única operação da Prop5 pode
    superar o mês inteiro da Montseguro sem que isso signifique performance
    melhor. Comparabilidade exige normalização.
    """
    linhas = []
    for e in Empresa.objects.all():
        r = ritmo(e, p)
        f = q.funil(e, p)
        vol = {x["estagio"]: x["volume"] for x in f["etapas"]}
        conv = (vol.get("S6", 0) / vol["S1"]) if vol.get("S1") else None
        maturidade = f["maturidade"]
        realizacao, _, _ = q.taxa_realizacao(e, p)
        inv = float(q.investimento(e, p))
        clientes = q.novos_clientes_coorte(e, p)
        rec_atr = float(q.receita_atribuida(e, p))
        ativos = e.responsaveis.filter(ativo=True).count()
        anterior = float(q.receita(e, mes_anterior(p)))
        atual = r.realizado
        linhas.append({
            "empresa": e.slug, "nome": e.nome, "cor": e.cor, "status": r.status,
            "atingimento_ritmo": r.atingimento_ritmo,
            "conv_s1_s6": conv,
            # Coorte imatura ainda não teve tempo de converter: o front marca a
            # célula em vez de deixar o número parecer performance ruim.
            "maturidade_coorte": maturidade,
            "taxa_realizacao": realizacao,
            "ciclo_medio": q.ciclo_medio(e, p),
            "cac": (inv / clientes) if clientes else None,
            "roas": (rec_atr / inv) if inv else None,
            "cobertura_pipeline": r.cobertura_pipeline,
            "produtividade": (atual / ativos) if ativos else None,
            "crescimento": ((atual - anterior) / anterior) if anterior else None,
        })
    return linhas


def overview(rotulo: str) -> dict:
    p = mes(rotulo)
    ant = mes_anterior(p)
    empresas = list(Empresa.objects.all())

    rrg = float(q.receita(None, p))
    rrg_ant = float(q.receita(None, ant))
    vig = float(q.volume_intermediado(None, p))
    meta_total = sum(float(q.meta(e, p) or 0) for e in empresas)
    forecast_total = sum(ritmo(e, p).forecast or 0 for e in empresas)
    serie_rrg = [float(q.receita(None, x)) for x in ultimos_meses(rotulo, 12)]

    inv = float(q.investimento(None, p))
    clientes = q.novos_clientes_coorte(None, p)
    coorte_madura = ultimos_meses(rotulo, 4)[0]
    realizacao, concl, tot = q.taxa_realizacao(None, p)

    # Conversão consolidada do grupo, na coorte do período.
    s1 = s6 = 0
    for e in empresas:
        vol = {x["estagio"]: x["volume"] for x in q.funil(e, p)["etapas"]}
        s1 += vol.get("S1", 0)
        s6 += vol.get("S6", 0)

    return {
        "periodo": {"rotulo": p.rotulo, "inicio": p.inicio.isoformat(), "fim": p.fim.isoformat(),
                    "dias_uteis_decorridos": p.dias_uteis_decorridos,
                    "dias_uteis_totais": p.dias_uteis_totais,
                    "em_andamento": p.em_andamento},
        "consolidado": {
            "rrg": medir("rrg", rrg, anterior=rrg_ant, meta=meta_total or None,
                         tendencia=serie_rrg).to_dict(),
            "vig": medir("vig", vig, detalhe="Escala da operação — nunca somado à RRG").to_dict(),
            "forecast": medir("forecast", forecast_total, meta=meta_total or None,
                              status=("verde" if forecast_total >= meta_total * 0.98
                                      else "amarelo" if forecast_total >= meta_total * 0.90
                                      else "vermelho") if meta_total else "cinza").to_dict(),
            "cac": medir("cac", (inv / clientes) if clientes else None,
                         detalhe=f"{clientes} novos clientes").to_dict(),
            # ROAS da coorte madura mais recente (90 dias). Usar a coorte do mês
            # corrente mostraria imaturidade e seria lido como ineficiência.
            "roas": medir("roas", q.roas_coorte(None, coorte_madura, 90),
                          detalhe=f"Coorte de {coorte_madura.rotulo}, madura em 90 dias").to_dict(),
            "conv_s1_s6": medir("conv_s1_s6", (s6 / s1) if s1 else None,
                                detalhe=f"{s6} de {s1} na coorte").to_dict(),
            "taxa_realizacao": medir("taxa_realizacao", realizacao,
                                     detalhe=f"{concl} de {tot} contratos "
                                             f"(janela defasada em {q.DEFASAGEM_REALIZACAO} dias)").to_dict(),
        },
        "empresas": [cartao_empresa(e, p) for e in empresas],
        "comparacao": comparacao(p),
    }

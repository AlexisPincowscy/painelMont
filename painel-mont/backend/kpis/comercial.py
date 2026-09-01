"""
Tela Comercial: funis comparados, gargalo, ciclo, pipeline e produtividade.

As etapas não são iguais nas três empresas — e não deveriam ser. O que torna a
comparação possível é a tabela de tradução (dim_estagio_canonico): cada empresa
mantém o nome real do seu estágio, e o grupo lê tudo por S1..S6.
"""
from __future__ import annotations

from core.models import Empresa

from . import consultas as q
from .grupo import ritmo
from .periodo import mes, mes_anterior
from .registry import medir


def tela(rotulo: str, empresa_slug: str | None = None) -> dict:
    p = mes(rotulo)
    ant = mes_anterior(p)
    empresas = list(Empresa.objects.filter(slug=empresa_slug)) if empresa_slug \
        else list(Empresa.objects.all())

    funis, gargalos, pipelines, rankings = [], [], [], []
    for e in empresas:
        f = q.funil(e, p)
        funis.append({"empresa": e.slug, "nome": e.nome, "cor": e.cor, **f})

        g = q.gargalo(e, p)
        if g:
            gargalos.append({"empresa": e.slug, "nome": e.nome, "cor": e.cor, **g})

        bruto, ponderado = q.pipeline_ponderado(e)
        r = ritmo(e, p)
        pipelines.append({
            "empresa": e.slug, "nome": e.nome, "cor": e.cor,
            "bruto": float(bruto), "ponderado": float(ponderado),
            "cobertura": r.cobertura_pipeline, "aging": q.aging_pipeline(e),
            "por_estagio": _pipeline_por_estagio(e),
        })
        rankings.append({"empresa": e.slug, "nome": e.nome, "cor": e.cor,
                         "linhas": q.ranking_responsaveis(e, p)})

    ciclos = [{"empresa": e.slug, "nome": e.nome, "cor": e.cor,
               "ciclo": q.ciclo_medio(e, p),
               "ciclo_anterior": q.ciclo_medio(e, ant),
               "esperado": e.ciclo_esperado_dias} for e in empresas]

    return {
        "periodo": p.rotulo,
        "empresa": empresa_slug,
        "kpis": [
            medir("conv_s1_s6", _conv_media(funis)).to_dict(),
            medir("ciclo_medio", _mediana([c["ciclo"] for c in ciclos if c["ciclo"]])).to_dict(),
            medir("cobertura_pipeline",
                  _media([x["cobertura"] for x in pipelines if x["cobertura"]])).to_dict(),
        ],
        "funis": funis,
        "gargalos": sorted(gargalos, key=lambda g: g["impacto_estimado"], reverse=True),
        "ciclos": ciclos,
        "pipelines": pipelines,
        "rankings": rankings,
    }


def _pipeline_por_estagio(empresa: Empresa) -> list[dict]:
    probs = q.probabilidades(empresa)
    traducao = {e.estagio_canonico: e.estagio_origem for e in empresa.estagios.all()}
    acc: dict[str, dict] = {}
    for op in empresa.oportunidades.filter(status="aberta").only("valor_potencial", "estagio_atual"):
        d = acc.setdefault(op.estagio_atual, {"bruto": 0.0, "ponderado": 0.0, "qtd": 0})
        d["bruto"] += float(op.valor_potencial)
        d["ponderado"] += float(op.valor_potencial) * probs.get(op.estagio_atual, 0.02)
        d["qtd"] += 1
    return [{"estagio": k, "rotulo": traducao.get(k, k),
             "probabilidade": probs.get(k), **v}
            for k, v in sorted(acc.items())]


def _conv_media(funis) -> float | None:
    s1 = sum(next((e["volume"] for e in f["etapas"] if e["estagio"] == "S1"), 0) for f in funis)
    s6 = sum(next((e["volume"] for e in f["etapas"] if e["estagio"] == "S6"), 0) for f in funis)
    return (s6 / s1) if s1 else None


def _media(vals):
    vals = [v for v in vals if v is not None]
    return sum(vals) / len(vals) if vals else None


def _mediana(vals):
    import statistics
    vals = [v for v in vals if v is not None]
    return float(statistics.median(vals)) if vals else None

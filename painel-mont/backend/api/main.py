"""
API analítica — FastAPI.

Divisão de responsabilidade com o Django:

  Django  → modelo de dados, migrations, carga, admin de verificação.
            É a camada que garante integridade e evolução do schema.
  FastAPI → a API que o front consome: contratos tipados com Pydantic,
            documentação OpenAPI automática e respostas assíncronas rápidas.

Os dois compartilham o MESMO ORM: o `django.setup()` abaixo carrega o app
Django dentro do processo FastAPI. Não há duplicação de modelo nem uma segunda
verdade sobre os dados.

Nenhuma rota calcula KPI. Toda rota delega para a camada semântica (`kpis/`),
que é o único lugar onde um indicador é definido.
"""
import os

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from django.conf import settings  # noqa: E402
from fastapi import FastAPI, HTTPException, Query  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402

from core.models import Empresa  # noqa: E402
from kpis import alertas as alertas_mod  # noqa: E402
from kpis import comercial, definicoes, empresa as empresa_mod, grupo, marketing  # noqa: E402,F401
from kpis import saude_dados  # noqa: E402
from kpis import periodo as per  # noqa: E402
from kpis.registry import catalogo  # noqa: E402

from .schemas import ( # noqa: E402
    AlertaOut,
    CatalogoItem,
    EmpresaOut,
    Envelope,
    Saude,
)

app = FastAPI(
    title="Painel Executivo · Grupo Mont",
    version="1.0.0",
    description=(
        "API analítica do Dashboard Executivo do Grupo Mont.\n\n"
        "Toda resposta é envelopada com `dados_demonstrativos`. Enquanto a base "
        "oficial não for disponibilizada, esse campo é `true` e a interface "
        "exibe um aviso permanente — a seção 14 do briefing rejeita dado "
        "inexistente apresentado como real."
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["GET"],
    allow_headers=["*"],
)


def _envelope(dados: dict | list) -> dict:
    return {
        "dados_demonstrativos": settings.DADOS_DEMONSTRATIVOS,
        "gerado_em": per.hoje().isoformat(),
        "dados": dados,
    }


def _periodo(p: str | None) -> str:
    rotulo = p or per.rotulo_atual()
    try:
        per.mes(rotulo)
    except Exception:
        raise HTTPException(400, "Período inválido. Use o formato AAAA-MM.")
    return rotulo


# ---------------------------------------------------------------------------
@app.get("/api/saude", response_model=Saude, tags=["meta"])
def saude():
    return Saude(
        ok=True,
        dados_demonstrativos=settings.DADOS_DEMONSTRATIVOS,
        empresas=Empresa.objects.count(),
        periodo_atual=per.rotulo_atual(),
    )


@app.get("/api/empresas", tags=["meta"])
def empresas():
    return _envelope([
        EmpresaOut(
            slug=e.slug, nome=e.nome, cor=e.cor, descricao=e.descricao,
            unidade_valor=e.unidade_valor, ciclo_esperado_dias=e.ciclo_esperado_dias,
            peso_forecast_ritmo=e.peso_forecast_ritmo,
        ).model_dump()
        for e in Empresa.objects.all()
    ])


@app.get("/api/periodos", tags=["meta"])
def periodos(n: int = 12):
    """Períodos disponíveis para o filtro global."""
    return _envelope([p.rotulo for p in reversed(per.ultimos_meses(per.rotulo_atual(), n))])


# --------------------------------------------------------------- 1. CEO
@app.get("/api/overview", tags=["telas"])
def overview(periodo: str | None = Query(None, description="AAAA-MM")):
    rotulo = _periodo(periodo)
    dados = grupo.overview(rotulo)
    dados["alertas"] = alertas_mod.topo(rotulo)
    return _envelope(dados)


# ---------------------------------------------------------- 2. Comercial
@app.get("/api/comercial", tags=["telas"])
def tela_comercial(periodo: str | None = None, empresa: str | None = None):
    return _envelope(comercial.tela(_periodo(periodo), empresa))


# ---------------------------------------------------------- 3. Marketing
@app.get("/api/marketing", tags=["telas"])
def tela_marketing(periodo: str | None = None, empresa: str | None = None):
    return _envelope(marketing.tela(_periodo(periodo), empresa))


# ----------------------------------------------------------- 4. Empresas
@app.get("/api/empresas/{slug}", tags=["telas"])
def tela_empresa(slug: str, periodo: str | None = None):
    if not Empresa.objects.filter(slug=slug).exists():
        raise HTTPException(404, f"Empresa desconhecida: {slug}")
    return _envelope(empresa_mod.tela(slug, _periodo(periodo)))


# ------------------------------------------------------------ 5. Insights
@app.get("/api/insights", tags=["telas"])
def insights(periodo: str | None = None):
    rotulo = _periodo(periodo)
    todos = alertas_mod.avaliar(rotulo)
    return _envelope({
        "periodo": rotulo,
        "alertas": todos,
        "resumo": {
            "alta": sum(1 for a in todos if a["severidade"] == "alta"),
            "media": sum(1 for a in todos if a["severidade"] == "media"),
            "oportunidade": sum(1 for a in todos if a["severidade"] == "oportunidade"),
            "impacto_total": sum(abs(a["quanto_custa"] or 0) for a in todos
                                 if a["severidade"] != "oportunidade"),
        },
        "comparacao": grupo.comparacao(per.mes(rotulo)),
    })


# ------------------------------------------------- 6. Saúde dos Dados
@app.get("/api/saude-dados", tags=["telas"])
def tela_saude_dados(periodo: str | None = None):
    """
    Adição própria à estrutura mínima da seção 4.

    Mede a completude dos campos críticos, nomeia os KPIs bloqueados por cada
    campo ausente e mostra quem registra bem. É o que transforma a lista de
    dados faltantes da seção 13 em acompanhamento de gestão, em vez de uma
    queixa em slide.
    """
    return _envelope(saude_dados.tela(_periodo(periodo)))


# ------------------------------------------------------- Documentação KPI
@app.get("/api/kpis", response_model=list[CatalogoItem], tags=["documentação"])
def kpis(escopo: str | None = Query(None, description="grupo | marketing | slug da empresa")):
    """
    Entregável 15.4 do briefing servido como dado.

    A ficha de cada KPI (nome, finalidade, fórmula, fonte, interpretação, dono,
    limiares e armadilha) vive no mesmo arquivo que define o cálculo. É o que
    alimenta o tooltip "como é calculado" de cada card e o que impede a clássica
    discussão de reunião "esse número está errado".
    """
    return catalogo(escopo)

"""
Testes de CONTRATO da API — prioridade 4.

Garantem que o front não quebra quando o modelo evolui, e que a promessa
central da arquitetura se mantém: nenhuma métrica chega à tela sem valor,
unidade, status e documentação embarcada.
"""
import pytest
from django.core.management import call_command
from fastapi.testclient import TestClient

from api.main import app

pytestmark = pytest.mark.django_db

PERIODO = "2026-08"


@pytest.fixture(scope="module")
def cliente(django_db_setup, django_db_blocker):
    with django_db_blocker.unblock():
        call_command("seed_demo", "--reset", verbosity=0)
        yield TestClient(app)


def _dados(resp):
    assert resp.status_code == 200, resp.text
    corpo = resp.json()
    # A flag de dados demonstrativos acompanha TODA resposta: é o que impede a
    # interface de apresentar dado sintético como se fosse real.
    assert corpo["dados_demonstrativos"] is True
    return corpo["dados"]


def test_saude(cliente):
    r = cliente.get("/api/saude").json()
    assert r["ok"] and r["empresas"] == 3


def test_overview_traz_as_tres_empresas_e_alertas(cliente):
    d = _dados(cliente.get(f"/api/overview?periodo={PERIODO}"))
    assert len(d["empresas"]) == 3
    assert d["consolidado"]["rrg"]["valor"] > 0
    assert len(d["alertas"]) <= 5           # no máximo cinco na tela do CEO
    assert d["comparacao"]


def test_toda_metrica_do_overview_tem_documentacao(cliente):
    """A promessa da camada semântica: o componente pede o indicador e recebe
    valor, unidade, status e ficha — nunca só o número."""
    d = _dados(cliente.get(f"/api/overview?periodo={PERIODO}"))
    for chave, m in d["consolidado"].items():
        assert {"valor", "unidade", "status", "doc"} <= set(m), chave
        assert m["doc"]["formula"], chave


def test_rrg_e_vig_sao_grandezas_separadas(cliente):
    d = _dados(cliente.get(f"/api/overview?periodo={PERIODO}"))
    assert d["consolidado"]["rrg"]["slug"] == "rrg"
    assert d["consolidado"]["vig"]["slug"] == "vig"
    assert d["consolidado"]["vig"]["valor"] > d["consolidado"]["rrg"]["valor"]


def test_comercial_respeita_o_funil_de_cada_empresa(cliente):
    """Os rótulos de etapa vêm da tabela de tradução: as três empresas NÃO
    mostram os mesmos nomes."""
    d = _dados(cliente.get(f"/api/comercial?periodo={PERIODO}"))
    rotulos = {f["empresa"]: [e["rotulo"] for e in f["etapas"]] for f in d["funis"]}
    assert rotulos["montseguro"][3] == "Cotação"
    assert rotulos["prop5"][3] == "Diagnóstico financeiro"
    assert rotulos["techbrabo"][3] == "Reunião + diagnóstico"


def test_marketing_devolve_cascata_canais_e_coortes(cliente):
    d = _dados(cliente.get(f"/api/marketing?periodo={PERIODO}"))
    assert [e["rotulo"] for e in d["cascata"]][0] == "Investimento"
    assert d["canais"]
    assert all("roas" in c and "roas_caixa" in c for c in d["canais"])
    assert len(d["coortes"]) == 6


def test_canal_sem_investimento_e_marcado_e_nao_rateado(cliente):
    """Ratear verba para canal orgânico seria inventar dado. O painel diz que
    não há investimento direto em vez de estimar um."""
    d = _dados(cliente.get(f"/api/marketing?periodo={PERIODO}"))
    organicos = [c for c in d["canais"] if c["sem_investimento_direto"]]
    assert organicos
    assert all(c["cac"] is None and c["cpl"] is None for c in organicos)


def test_cada_empresa_tem_kpis_proprios(cliente):
    """O briefing rejeita os mesmos KPIs repetidos nas três empresas."""
    conjuntos = {}
    for slug in ("montseguro", "prop5", "techbrabo"):
        d = _dados(cliente.get(f"/api/empresas/{slug}?periodo={PERIODO}"))
        conjuntos[slug] = {k["slug"] for k in d["kpis"]}
        assert len(conjuntos[slug]) >= 10
    assert not conjuntos["montseguro"] & conjuntos["prop5"]
    assert not conjuntos["prop5"] & conjuntos["techbrabo"]
    assert not conjuntos["montseguro"] & conjuntos["techbrabo"]


def test_kpi_sem_dado_e_declarado_e_nao_estimado(cliente):
    d = _dados(cliente.get(f"/api/empresas/techbrabo?periodo={PERIODO}"))
    churn = next(k for k in d["kpis"] if k["slug"] == "tb_churn")
    assert churn["valor"] is None
    assert churn["status"] == "cinza"
    assert "data_cancelamento" in churn["indisponivel_por"]


def test_alerta_tem_as_cinco_perguntas_e_um_destino(cliente):
    d = _dados(cliente.get(f"/api/insights?periodo={PERIODO}"))
    assert d["alertas"]
    for a in d["alertas"]:
        for campo in ("o_que_houve", "por_que_importa", "o_que_fazer", "quem", "destino"):
            assert a[campo], (a["regra"], campo)
        assert a["severidade"] in ("alta", "media", "oportunidade")


def test_alertas_vem_ordenados_por_severidade(cliente):
    d = _dados(cliente.get(f"/api/insights?periodo={PERIODO}"))
    scores = [a["score"] for a in d["alertas"]]
    assert scores == sorted(scores, reverse=True)


def test_catalogo_de_kpis_e_servido_pela_api(cliente):
    """Entregável 15.4: a documentação vive no mesmo lugar que o cálculo."""
    itens = cliente.get("/api/kpis").json()
    assert len(itens) > 40
    for k in itens:
        assert k["formula"] and k["fonte"] and k["interpretacao"]


def test_empresa_inexistente_devolve_404(cliente):
    assert cliente.get("/api/empresas/inexistente").status_code == 404


def test_periodo_invalido_devolve_400(cliente):
    assert cliente.get("/api/overview?periodo=agosto").status_code == 400


# --------------------------------------------------- 6. Saúde dos Dados
def test_saude_dados_mede_completude_e_nomeia_kpis_bloqueados(cliente):
    """
    A tela que transforma dado faltante em acompanhamento.

    O contrato importante: cada campo declara os KPIs que dependem dele. Sem
    isso a tela viraria uma lista de percentuais sem consequência.
    """
    d = _dados(cliente.get(f"/api/saude-dados?periodo={PERIODO}"))
    assert d["completude"]
    for linha in d["completude"]:
        assert linha["campo"] and linha["momento"] and linha["por_que"]
        assert linha["kpis_dependentes"], linha["campo"]
        assert len(linha["por_empresa"]) == 3
    assert 0 <= d["indice_geral"] <= 1


def test_completude_usa_janela_movel_e_expoe_a_amostra(cliente):
    """Completude é higiene, não período: medir no mês daria n=3 na TechBrabo."""
    d = _dados(cliente.get(f"/api/saude-dados?periodo={PERIODO}"))
    assert d["janela"]["dias"] >= 90
    for linha in d["completude"]:
        for c in linha["por_empresa"]:
            # Células estruturais (existe / não existe) não têm amostra: a regra
            # abaixo vale só para as que de fato medem preenchimento.
            if c["aplicavel"] and not c.get("estrutural") and not c.get("inexistente"):
                assert "total" in c
                # Amostra pequena não pinta semáforo — não dá autoridade a um
                # percentual que não a tem.
                if c["total"] < d["amostra_minima"]:
                    assert c["status"] == "cinza"


def test_campo_inexistente_e_diferente_de_campo_vazio(cliente):
    """`data_cancelamento` só existe na Montseguro — e é por isso que o churn da
    TechBrabo aparece indisponível. Zero de zero esconderia isso."""
    d = _dados(cliente.get(f"/api/saude-dados?periodo={PERIODO}"))
    linha = next(l for l in d["completude"] if "data_cancelamento" in l["campo"])
    por_slug = {c["empresa"]: c for c in linha["por_empresa"]}
    assert por_slug["techbrabo"].get("inexistente") is True
    assert por_slug["montseguro"].get("inexistente") is not True
    # Ambas são verificações ESTRUTURAIS: nenhuma reporta taxa de preenchimento,
    # porque o campo é opcional por natureza e uma taxa não significaria nada.
    assert por_slug["montseguro"].get("estrutural") is True
    assert por_slug["montseguro"]["taxa"] is None


def test_lista_de_kpis_bloqueados_vem_da_camada_semantica(cliente):
    """A lista não é mantida à mão: sai de quem declara `indisponivel_por`."""
    d = _dados(cliente.get(f"/api/saude-dados?periodo={PERIODO}"))
    slugs = {b["slug"] for b in d["kpis_bloqueados"]}
    assert "tb_churn" in slugs
    for b in d["kpis_bloqueados"]:
        assert b["motivo"]


def test_registro_por_responsavel_vem_ordenado_do_pior(cliente):
    d = _dados(cliente.get(f"/api/saude-dados?periodo={PERIODO}"))
    gerais = [r["geral"] for r in d["responsaveis"]]
    assert gerais == sorted(gerais)

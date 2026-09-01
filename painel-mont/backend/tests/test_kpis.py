"""
Testes das FÓRMULAS de KPI — prioridade 1 da estratégia de testes.

Justificativa: em um painel executivo, o bug mais caro não quebra a tela. Ele
mostra um número errado com aparência de certo, e alguém decide com base nele.
Por isso os casos de borda (divisão por zero, período sem meta, amostra vazia)
importam mais aqui do que em qualquer outra camada.
"""
import datetime as dt
from decimal import Decimal

import pytest

from kpis import definicoes  # noqa: F401  — registra o catálogo
from kpis.periodo import Periodo, dias_uteis, mes, mes_anterior, ultimos_meses
from kpis.registry import REGISTRO, KpiDef, catalogo, medir


# ---------------------------------------------------------------- registro
def test_catalogo_nao_esta_vazio():
    assert len(REGISTRO) > 40


def test_todo_kpi_tem_ficha_completa():
    """Seção 15.4: nome, finalidade, fórmula, fonte e interpretação são
    obrigatórios. Um KPI sem ficha não pode chegar à tela."""
    for slug, kpi in REGISTRO.items():
        assert kpi.nome, slug
        assert kpi.finalidade, slug
        assert kpi.formula, slug
        assert kpi.fonte, slug
        assert kpi.interpretacao, slug


def test_kpis_com_limiar_declaram_sentido():
    for slug, kpi in REGISTRO.items():
        if kpi.limiares:
            assert kpi.sentido in ("maior_melhor", "menor_melhor"), slug


def test_catalogo_filtra_por_escopo():
    grupo = catalogo("grupo")
    assert grupo and all(k["escopo"] == "grupo" for k in grupo)


# ------------------------------------------------------------- semáforo
def test_status_maior_melhor():
    k = KpiDef(slug="x", nome="x", finalidade="f", formula="f", fonte="f",
               interpretacao="i", sentido="maior_melhor", limiares=(0.95, 0.85))
    assert k.status(1.00) == "verde"
    assert k.status(0.95) == "verde"       # limite inclusivo
    assert k.status(0.90) == "amarelo"
    assert k.status(0.84) == "vermelho"


def test_status_menor_melhor():
    k = KpiDef(slug="y", nome="y", finalidade="f", formula="f", fonte="f",
               interpretacao="i", sentido="menor_melhor", limiares=(1.10, 1.30))
    assert k.status(1.00) == "verde"
    assert k.status(1.20) == "amarelo"
    assert k.status(1.31) == "vermelho"


def test_status_cinza_quando_nao_ha_valor():
    """Sem dado, o painel diz que não sabe — não estima."""
    k = KpiDef(slug="z", nome="z", finalidade="f", formula="f", fonte="f",
               interpretacao="i", limiares=(1, 2))
    assert k.status(None) == "cinza"


def test_status_cinza_sem_limiar():
    k = KpiDef(slug="w", nome="w", finalidade="f", formula="f", fonte="f", interpretacao="i")
    assert k.status(999) == "cinza"


# --------------------------------------------------------------- métrica
def test_metrica_embarca_a_documentacao():
    """O tooltip 'como é calculado' não é um texto solto na tela: vem do mesmo
    lugar que define o cálculo."""
    m = medir("cac", 1200.0, anterior=1000.0)
    assert m.doc["formula"]
    assert m.doc["armadilha"]
    assert m.variacao == pytest.approx(0.20)


def test_variacao_nao_divide_por_zero():
    assert medir("cac", 50.0, anterior=0).variacao is None
    assert medir("cac", 50.0, anterior=None).variacao is None


def test_variacao_none_quando_valor_ausente():
    assert medir("cac", None, anterior=100.0).variacao is None


def test_indisponibilidade_e_explicita():
    m = medir("tb_churn", None, indisponivel_por="falta data_cancelamento")
    assert m.status == "cinza"
    assert "data_cancelamento" in m.indisponivel_por


# ---------------------------------------------------------------- período
def test_dias_uteis_ignora_fim_de_semana():
    # 2026-08-01 é sábado; 2026-08-31 é segunda.
    assert dias_uteis(dt.date(2026, 8, 1), dt.date(2026, 8, 2)) == 0
    assert dias_uteis(dt.date(2026, 8, 3), dt.date(2026, 8, 7)) == 5


def test_dias_uteis_intervalo_invertido():
    assert dias_uteis(dt.date(2026, 8, 10), dt.date(2026, 8, 1)) == 0


def test_mes_calcula_ultimo_dia():
    assert mes("2026-02").fim == dt.date(2026, 2, 28)
    assert mes("2026-12").fim == dt.date(2026, 12, 31)


def test_mes_anterior_atravessa_o_ano():
    assert mes_anterior(mes("2026-01")).rotulo == "2025-12"


def test_ultimos_meses_em_ordem_cronologica():
    serie = ultimos_meses("2026-03", 3)
    assert [p.rotulo for p in serie] == ["2026-01", "2026-02", "2026-03"]


def test_fracao_decorrida_de_periodo_passado_e_um():
    p = mes("2026-05")
    assert p.fracao_decorrida == 1.0
    assert p.dias_uteis_restantes == 0


def test_fracao_decorrida_de_periodo_futuro_e_zero():
    p = mes("2026-12")
    assert p.fracao_decorrida == 0.0


def test_periodo_em_andamento_e_parcial():
    """Agosto/2026 está em curso na base demonstrativa: a fração decorrida
    precisa ficar entre 0 e 1, ou o cálculo de ritmo perde o sentido."""
    p = mes("2026-08")
    assert p.em_andamento
    assert 0 < p.fracao_decorrida < 1

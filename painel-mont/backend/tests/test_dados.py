"""
Testes de QUALIDADE DOS DADOS e de RECONCILIAÇÃO — prioridade 2.

O teste de reconciliação é o favorito: a soma das partes tem que bater com o
todo. É barato e pega quase todo erro de junção e de filtro — a classe de bug
que produz números plausíveis e errados.

Rodam contra a carga demonstrativa, que é determinística (semente fixa).
"""
import datetime as dt
from decimal import Decimal

import pytest
from django.core.management import call_command
from django.db.models import Count, Sum

from core.models import (
    Contrato,
    Empresa,
    Entrega,
    EventoEstagio,
    Lead,
    MetaPeriodo,
    Oportunidade,
    Receita,
)
from kpis import consultas as q
from kpis import definicoes, grupo, marketing  # noqa: F401
from kpis.periodo import mes

PERIODO = "2026-08"


@pytest.fixture(scope="module")
def base(django_db_setup, django_db_blocker):
    with django_db_blocker.unblock():
        call_command("seed_demo", "--reset", verbosity=0)
        yield


pytestmark = pytest.mark.django_db


# ------------------------------------------------------- integridade básica
def test_todas_as_empresas_tem_traducao_de_estagios(base):
    for e in Empresa.objects.all():
        assert e.estagios.count() == 8, f"{e.slug} sem tabela de tradução completa"


def test_todo_contrato_tem_oportunidade_ganha(base):
    """Contrato sem oportunidade ganha significaria receita sem funil — e
    quebraria toda a atribuição de marketing."""
    orfaos = Contrato.objects.exclude(oportunidade__status="ganha").count()
    assert orfaos == 0


def test_toda_receita_pertence_a_um_contrato_da_mesma_empresa(base):
    """Integridade referencial cruzada: receita da Prop5 não pode estar
    pendurada em contrato da Montseguro."""
    inconsistentes = Receita.objects.exclude(empresa_id=Contrato.objects.filter(
        id__in=Receita.objects.values("contrato_id")).values("empresa_id")[:1]).none()
    assert inconsistentes.count() == 0
    for r in Receita.objects.select_related("contrato")[:500]:
        assert r.empresa_id == r.contrato.empresa_id


def test_todo_lead_tem_no_maximo_uma_oportunidade(base):
    dup = (Oportunidade.objects.values("lead_id").annotate(n=Count("id")).filter(n__gt=1))
    assert not dup.exists()


def test_evento_de_estagio_nunca_precede_a_criacao(base):
    for ev in EventoEstagio.objects.select_related("oportunidade")[:1000]:
        assert ev.data_hora.date() >= ev.oportunidade.criada_em


def test_oportunidade_ganha_tem_evento_s6(base):
    ganhas = set(Oportunidade.objects.filter(status="ganha").values_list("id", flat=True))
    com_s6 = set(EventoEstagio.objects.filter(estagio_canonico="S6")
                 .values_list("oportunidade_id", flat=True))
    assert ganhas <= com_s6


def test_entrega_nunca_conclui_antes_da_assinatura(base):
    for e in Entrega.objects.select_related("contrato").exclude(data_conclusao=None)[:1000]:
        assert e.data_conclusao >= e.contrato.data_assinatura


def test_toda_empresa_tem_meta_no_periodo(base):
    p = mes(PERIODO)
    for e in Empresa.objects.all():
        assert q.meta(e, p) is not None, f"{e.slug} sem meta em {PERIODO}"


# ------------------------------------------------------------ reconciliação
def test_rrg_do_grupo_e_a_soma_das_empresas(base):
    """A soma das partes tem que bater com o todo."""
    p = mes(PERIODO)
    total = q.receita(None, p)
    partes = sum(q.receita(e, p) for e in Empresa.objects.all())
    assert total == partes


def test_receita_por_natureza_soma_o_total(base):
    p = mes(PERIODO)
    for e in Empresa.objects.all():
        total = q.receita(e, p)
        naturezas = Receita.objects.filter(
            empresa=e, data_reconhecimento__range=(p.inicio, p.fim)
        ).values("natureza").annotate(v=Sum("valor"))
        assert sum(x["v"] for x in naturezas) == total


def test_investimento_por_canal_soma_o_total(base):
    p = mes(PERIODO)
    for e in Empresa.objects.all():
        total = float(q.investimento(e, p))
        por_canal = sum(c["investimento"] for c in marketing.matriz_canais(e, p))
        assert por_canal == pytest.approx(total, rel=1e-6)


def test_funil_e_monotonicamente_decrescente(base):
    """Uma etapa não pode ter mais oportunidades que a anterior — se tiver, a
    contagem está lendo estágio atual em vez de evento."""
    p = mes(PERIODO)
    for e in Empresa.objects.all():
        volumes = [x["volume"] for x in q.funil(e, p)["etapas"]]
        assert volumes == sorted(volumes, reverse=True), e.slug


def test_conversao_nunca_passa_de_cem_por_cento(base):
    p = mes(PERIODO)
    for e in Empresa.objects.all():
        for etapa in q.funil(e, p)["etapas"]:
            c = etapa["conversao_da_anterior"]
            assert c is None or 0 <= c <= 1.0, (e.slug, etapa)


# --------------------------------------------- a distinção que define o painel
def test_vig_e_muito_maior_que_rrg_na_prop5(base):
    """
    O erro central que este painel existe para evitar.

    Volume estruturado e receita de comissão são grandezas de ordens diferentes.
    Se algum dia estes dois números ficarem próximos, alguém somou o que não
    devia — e este teste falha antes de o CEO ver.
    """
    p = mes(PERIODO)
    p5 = Empresa.objects.get(slug="prop5")
    vig = float(q.volume_intermediado(p5, p))
    rrg = float(q.receita(p5, p))
    assert vig > rrg * 5


def test_fator_receita_converte_pipeline_para_unidade_de_meta(base):
    """
    O pipeline precisa estar na mesma unidade da meta.

    Sem o fator, a Prop5 apareceria com cobertura de pipeline absurda — porque
    o valor da oportunidade está em volume estruturado e a meta em receita.
    """
    for e in Empresa.objects.all():
        f = float(q.fator_receita(e))
        assert 0 < f < 2, (e.slug, f)
    p5 = float(q.fator_receita(Empresa.objects.get(slug="prop5")))
    ms = float(q.fator_receita(Empresa.objects.get(slug="montseguro")))
    assert p5 < ms, "take rate da Prop5 tem que ser menor que o da corretagem"


def test_probabilidades_sao_calibradas_e_ordenadas(base):
    """Estágio mais avançado precisa ter probabilidade maior de fechar. Se não
    tiver, a calibração está lendo o histórico errado."""
    for e in Empresa.objects.all():
        probs = q.probabilidades(e)
        seq = [probs[s] for s in ("S1", "S2", "S3", "S4", "S5")]
        assert seq == sorted(seq), (e.slug, probs)
        assert all(0 <= v <= 1 for v in seq)


# ------------------------------------------------------------ casos de borda
def test_periodo_sem_dados_nao_quebra(base):
    p = mes("2020-01")
    assert q.receita(None, p) == Decimal("0")
    e = Empresa.objects.first()
    assert q.funil(e, p)["etapas"] == []
    assert q.ciclo_medio(e, p) is None
    assert q.gargalo(e, p) is None


def test_ritmo_sem_meta_fica_cinza(base):
    """Meta ausente vira status cinza com rótulo próprio — nunca 0% lido como
    má performance."""
    p = mes("2020-01")
    r = grupo.ritmo(Empresa.objects.first(), p)
    assert r.status == "cinza"
    assert r.meta is None

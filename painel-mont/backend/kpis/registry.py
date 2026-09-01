"""
CAMADA SEMÂNTICA — o coração da solução.

Regra de arquitetura: nenhum componente de tela calcula KPI. Um gráfico PEDE um
indicador e o recebe pronto, com valor, comparação com o período anterior,
posição contra a meta, tendência e status de semáforo.

É isso que garante que "CAC" na tela do CEO e "CAC" na tela de Marketing sejam
sempre o mesmo número — e é isso que permite servir a documentação do KPI
(entregável 15.4 do briefing) pela própria API, no tooltip "como é calculado".
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Literal

Unidade = Literal["BRL", "PCT", "DIAS", "UN", "X"]
Sentido = Literal["maior_melhor", "menor_melhor", "neutro"]
Status = Literal["verde", "amarelo", "vermelho", "cinza"]


@dataclass(frozen=True)
class KpiDef:
    """
    Ficha de documentação de um indicador.

    Os cinco primeiros campos são os exigidos pela seção 15.4 do briefing.
    Os três últimos foram acrescentados porque evitam discussão futura:
    quem responde pelo número, a partir de quando ele acende amarelo/vermelho,
    e como esse indicador engana quem o lê isolado.
    """

    slug: str
    nome: str
    finalidade: str
    formula: str
    fonte: str
    interpretacao: str
    dono: str = ""
    armadilha: str = ""
    unidade: Unidade = "UN"
    sentido: Sentido = "maior_melhor"
    escopo: str = "grupo"
    # (limite_verde, limite_amarelo) na escala do próprio indicador.
    limiares: tuple[float, float] | None = None

    def status(self, valor: float | None) -> Status:
        if valor is None or self.limiares is None:
            return "cinza"
        verde, amarelo = self.limiares
        if self.sentido == "maior_melhor":
            return "verde" if valor >= verde else ("amarelo" if valor >= amarelo else "vermelho")
        if self.sentido == "menor_melhor":
            return "verde" if valor <= verde else ("amarelo" if valor <= amarelo else "vermelho")
        return "cinza"


@dataclass
class Metrica:
    """O que a API devolve para um indicador. Nunca só o número."""

    slug: str
    nome: str
    valor: float | None
    unidade: Unidade
    status: Status = "cinza"
    anterior: float | None = None
    variacao: float | None = None          # variação relativa vs. período anterior
    meta: float | None = None
    tendencia: list[float] = field(default_factory=list)
    detalhe: str = ""
    # Documentação embarcada: é o tooltip "como é calculado" na tela.
    doc: dict = field(default_factory=dict)
    # Quando o dado não permite calcular com honestidade, dizemos isso em vez
    # de estimar. Um card cinza é mais útil que um número plausível e errado.
    indisponivel_por: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


REGISTRO: dict[str, KpiDef] = {}


def registrar(kpi: KpiDef) -> KpiDef:
    if kpi.slug in REGISTRO:
        raise ValueError(f"KPI duplicado no registro: {kpi.slug}")
    REGISTRO[kpi.slug] = kpi
    return kpi


def catalogo(escopo: str | None = None) -> list[dict]:
    """Serve a documentação de KPIs como dado — o entregável 15.4 vive no mesmo
    lugar que o cálculo, e por isso não envelhece em um documento paralelo."""
    itens = REGISTRO.values()
    if escopo:
        itens = [k for k in itens if k.escopo == escopo]
    return [
        {**asdict(k), "limiares": list(k.limiares) if k.limiares else None}
        for k in sorted(itens, key=lambda k: (k.escopo, k.nome))
    ]


def medir(
    slug: str,
    valor: float | None,
    *,
    anterior: float | None = None,
    meta: float | None = None,
    tendencia: list[float] | None = None,
    detalhe: str = "",
    status: Status | None = None,
    indisponivel_por: str = "",
) -> Metrica:
    """Fábrica única de métricas. Todo número que chega ao front passa por aqui."""
    kpi = REGISTRO[slug]
    variacao = None
    if valor is not None and anterior not in (None, 0):
        variacao = (valor - anterior) / abs(anterior)
    return Metrica(
        slug=kpi.slug,
        nome=kpi.nome,
        valor=valor,
        unidade=kpi.unidade,
        status=status or kpi.status(valor),
        anterior=anterior,
        variacao=variacao,
        meta=meta,
        tendencia=tendencia or [],
        detalhe=detalhe,
        indisponivel_por=indisponivel_por,
        doc={
            "finalidade": kpi.finalidade,
            "formula": kpi.formula,
            "fonte": kpi.fonte,
            "interpretacao": kpi.interpretacao,
            "dono": kpi.dono,
            "armadilha": kpi.armadilha,
            "sentido": kpi.sentido,
        },
    )

"""
Contratos da API (Pydantic).

Só os envelopes e os objetos de metadados são tipados estritamente. As telas
devolvem estruturas ricas e variáveis por empresa — tipá-las nó a nó criaria um
acoplamento que atrapalha mais do que ajuda, e a documentação real de cada
indicador vem embutida em `Metrica.doc`.
"""
from typing import Any

from pydantic import BaseModel, Field


class Saude(BaseModel):
    ok: bool
    dados_demonstrativos: bool
    empresas: int
    periodo_atual: str


class EmpresaOut(BaseModel):
    slug: str
    nome: str
    cor: str
    descricao: str
    unidade_valor: str
    ciclo_esperado_dias: int
    peso_forecast_ritmo: float = Field(
        description="Peso do componente de ritmo no forecast híbrido desta empresa.")


class Envelope(BaseModel):
    dados_demonstrativos: bool = Field(
        description="Enquanto true, a interface exibe aviso permanente de dados de demonstração.")
    gerado_em: str
    dados: Any


class CatalogoItem(BaseModel):
    slug: str
    nome: str
    finalidade: str
    formula: str
    fonte: str
    interpretacao: str
    dono: str = ""
    armadilha: str = ""
    unidade: str
    sentido: str
    escopo: str
    limiares: list[float] | None = None


class AlertaOut(BaseModel):
    regra: str
    titulo: str
    severidade: str
    camada: str
    empresa: str
    empresa_nome: str
    o_que_houve: str
    por_que_importa: str
    quanto_custa: float | None
    o_que_fazer: str
    quem: str
    prazo_dias: int
    destino: str
    score: float
    confianca: float

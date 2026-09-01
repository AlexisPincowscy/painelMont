"""
Aritmética de período e de ritmo.

O briefing (seção 9) é explícito: meta não é percentual, é ritmo. Este módulo
resolve "onde deveríamos estar hoje", que é a pergunta que percentual de meta
não responde.

Decisão: o ritmo é medido em DIAS ÚTEIS, não em dias corridos. Um mês que
começa no sábado tem o mesmo número de dias corridos e menos capacidade de
produção — usar dia corrido faz toda segunda-feira parecer um atraso.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

HOJE_FIXO = dt.date(2026, 8, 27)  # base demonstrativa; em produção, date.today()


def hoje() -> dt.date:
    return HOJE_FIXO


@dataclass(frozen=True)
class Periodo:
    inicio: dt.date
    fim: dt.date
    rotulo: str

    @property
    def dias_uteis_totais(self) -> int:
        return dias_uteis(self.inicio, self.fim)

    @property
    def dias_uteis_decorridos(self) -> int:
        corte = min(self.fim, hoje())
        if corte < self.inicio:
            return 0
        return dias_uteis(self.inicio, corte)

    @property
    def fracao_decorrida(self) -> float:
        total = self.dias_uteis_totais
        return min(1.0, self.dias_uteis_decorridos / total) if total else 0.0

    @property
    def em_andamento(self) -> bool:
        return self.inicio <= hoje() <= self.fim

    @property
    def dias_uteis_restantes(self) -> int:
        return max(0, self.dias_uteis_totais - self.dias_uteis_decorridos)


def dias_uteis(inicio: dt.date, fim: dt.date) -> int:
    if fim < inicio:
        return 0
    dias = 0
    d = inicio
    while d <= fim:
        if d.weekday() < 5:
            dias += 1
        d += dt.timedelta(days=1)
    return dias


def mes(rotulo: str) -> Periodo:
    """rotulo no formato AAAA-MM."""
    ano, m = (int(x) for x in rotulo.split("-"))
    inicio = dt.date(ano, m, 1)
    fim = (dt.date(ano + 1, 1, 1) if m == 12 else dt.date(ano, m + 1, 1)) - dt.timedelta(days=1)
    return Periodo(inicio, fim, rotulo)


def mes_anterior(p: Periodo) -> Periodo:
    ultimo = p.inicio - dt.timedelta(days=1)
    return mes(f"{ultimo.year}-{ultimo.month:02d}")


def ultimos_meses(rotulo: str, n: int) -> list[Periodo]:
    """Série histórica terminando no período informado — base das tendências."""
    p = mes(rotulo)
    saida = [p]
    for _ in range(n - 1):
        p = mes_anterior(p)
        saida.append(p)
    return list(reversed(saida))


def rotulo_atual() -> str:
    h = hoje()
    return f"{h.year}-{h.month:02d}"

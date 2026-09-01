import type { Unidade } from "./types";

/**
 * Formatação em um lugar só.
 *
 * Regra do painel: nenhum número aparece sozinho. A formatação carrega a
 * unidade, e a comparação com o período anterior vem sempre ao lado.
 */
const brl = new Intl.NumberFormat("pt-BR", {
  style: "currency",
  currency: "BRL",
  maximumFractionDigits: 0,
});
const brlCompacto = new Intl.NumberFormat("pt-BR", {
  style: "currency",
  currency: "BRL",
  notation: "compact",
  maximumFractionDigits: 1,
});
const inteiro = new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 0 });

export function fmt(valor: number | null, unidade: Unidade, compacto = false): string {
  if (valor === null || valor === undefined || Number.isNaN(valor)) return "—";
  switch (unidade) {
    case "BRL":
      return compacto || Math.abs(valor) >= 1_000_000 ? brlCompacto.format(valor) : brl.format(valor);
    case "PCT":
      return `${(valor * 100).toFixed(1).replace(".", ",")}%`;
    case "DIAS":
      return `${inteiro.format(valor)} d`;
    case "X":
      return `${valor.toFixed(2).replace(".", ",")}×`;
    default:
      return inteiro.format(valor);
  }
}

export function pct(v: number | null, casas = 1): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  return `${(v * 100).toFixed(casas).replace(".", ",")}%`;
}

export function dinheiro(v: number | null, compacto = false): string {
  return fmt(v, "BRL", compacto);
}

export function variacao(v: number | null): { texto: string; sinal: 1 | -1 | 0 } {
  if (v === null || v === undefined || Number.isNaN(v)) return { texto: "—", sinal: 0 };
  const sinal = v > 0.0005 ? 1 : v < -0.0005 ? -1 : 0;
  const seta = sinal === 1 ? "▲" : sinal === -1 ? "▼" : "•";
  return { texto: `${seta} ${Math.abs(v * 100).toFixed(1).replace(".", ",")}%`, sinal };
}

/**
 * Um KPI "menor é melhor" que sobe é uma notícia ruim, mesmo com a seta para
 * cima. A cor da variação segue o SENTIDO do indicador, não a direção da seta.
 */
export function corVariacao(sinal: -1 | 0 | 1, sentido: string): string {
  if (sinal === 0) return "var(--muted)";
  const bom = sentido === "menor_melhor" ? sinal === -1 : sinal === 1;
  if (sentido === "neutro") return "var(--muted)";
  return bom ? "var(--ok)" : "var(--risk)";
}

export function rotuloMes(rotulo: string): string {
  const nomes = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"];
  const [ano, mes] = rotulo.split("-");
  return `${nomes[Number(mes) - 1]}/${ano.slice(2)}`;
}

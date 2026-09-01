/**
 * Tipos espelhando os contratos da API.
 *
 * `Metrica` é o tipo central: nenhum componente de tela recebe um número solto.
 * Ele recebe valor, unidade, status, comparação, tendência e a ficha do KPI —
 * e por isso nenhum componente precisa (nem pode) calcular indicador.
 */
export type Unidade = "BRL" | "PCT" | "DIAS" | "UN" | "X";
export type Status = "verde" | "amarelo" | "vermelho" | "cinza";

export interface DocKpi {
  finalidade: string;
  formula: string;
  fonte: string;
  interpretacao: string;
  dono: string;
  armadilha: string;
  sentido: string;
}

export interface Metrica {
  slug: string;
  nome: string;
  valor: number | null;
  unidade: Unidade;
  status: Status;
  anterior: number | null;
  variacao: number | null;
  meta: number | null;
  tendencia: number[];
  detalhe: string;
  doc: DocKpi;
  indisponivel_por: string;
}

export interface Empresa {
  slug: string;
  nome: string;
  cor: string;
  descricao: string;
  unidade_valor: string;
  ciclo_esperado_dias?: number;
  peso_forecast_ritmo?: number;
}

export interface Ritmo {
  meta: number | null;
  realizado: number;
  meta_esperada_hoje: number | null;
  gap: number | null;
  atingimento_ritmo: number | null;
  forecast: number | null;
  necessidade_diaria: number | null;
  indice_esforco: number | null;
  cobertura_pipeline: number | null;
  pipeline_bruto: number;
  pipeline_ponderado: number;
  dias_uteis_decorridos: number;
  dias_uteis_totais: number;
  peso_ritmo: number;
  status: Status;
}

export interface Alerta {
  regra: string;
  titulo: string;
  severidade: "alta" | "media" | "oportunidade";
  camada: string;
  empresa: string;
  empresa_nome: string;
  o_que_houve: string;
  por_que_importa: string;
  quanto_custa: number | null;
  o_que_fazer: string;
  quem: string;
  prazo_dias: number;
  destino: string;
  score: number;
  confianca: number;
}

export interface EtapaFunil {
  estagio: string;
  rotulo: string;
  rotulo_anterior: string | null;
  volume: number;
  conversao_da_anterior: number | null;
  perda: number;
}

export interface Funil {
  empresa: string;
  nome: string;
  cor: string;
  etapas: EtapaFunil[];
  coorte: number;
  maturidade: number;
}

export interface LinhaComparacao {
  empresa: string;
  nome: string;
  cor: string;
  status: Status;
  atingimento_ritmo: number | null;
  conv_s1_s6: number | null;
  maturidade_coorte?: number;
  taxa_realizacao: number | null;
  ciclo_medio: number | null;
  cac: number | null;
  roas: number | null;
  cobertura_pipeline: number | null;
  produtividade: number | null;
  crescimento: number | null;
}

export interface Overview {
  periodo: {
    rotulo: string;
    inicio: string;
    fim: string;
    dias_uteis_decorridos: number;
    dias_uteis_totais: number;
    em_andamento: boolean;
  };
  consolidado: Record<string, Metrica>;
  empresas: { empresa: Empresa; ritmo: Ritmo; receita: Metrica; vig: Metrica }[];
  comparacao: LinhaComparacao[];
  alertas: Alerta[];
}

export interface Canal {
  canal: string;
  slug: string;
  pago: boolean;
  investimento: number;
  leads: number;
  qualificados: number;
  clientes: number;
  receita: number;
  cpl: number | null;
  cpl_qualificado: number | null;
  aproveitamento: number | null;
  cac: number | null;
  roas: number | null;
  roas_caixa: number | null;
  coorte_madura: boolean;
  participacao_verba: number;
  sem_investimento_direto: boolean;
}

export interface TelaMarketing {
  periodo: string;
  empresa: string | null;
  kpis: Metrica[];
  cascata: { rotulo: string; valor: number; unidade: Unidade; passagem: number | null }[];
  canais: Canal[];
  coortes: {
    coorte: string;
    investimento: number;
    leads: number;
    roas_30: number | null;
    roas_60: number | null;
    roas_90: number | null;
  }[];
}

export interface TelaComercial {
  periodo: string;
  empresa: string | null;
  kpis: Metrica[];
  funis: Funil[];
  gargalos: (EtapaFunil & {
    empresa: string;
    nome: string;
    cor: string;
    impacto_estimado: number;
  })[];
  ciclos: { empresa: string; nome: string; cor: string; ciclo: number | null; ciclo_anterior: number | null; esperado: number }[];
  pipelines: {
    empresa: string;
    nome: string;
    cor: string;
    bruto: number;
    ponderado: number;
    cobertura: number | null;
    aging: number | null;
    por_estagio: { estagio: string; rotulo: string; probabilidade: number | null; bruto: number; ponderado: number; qtd: number }[];
  }[];
  rankings: {
    empresa: string;
    nome: string;
    cor: string;
    linhas: { nome: string; ativo: boolean; receita: number; oportunidades: number; ganhas: number; conversao: number | null }[];
  }[];
}

export interface TelaEmpresa {
  empresa: Empresa;
  periodo: string;
  ritmo: Ritmo;
  kpis: Metrica[];
  funil: { etapas: EtapaFunil[]; coorte: number; maturidade: number };
  probabilidades: Record<string, number>;
}

export interface TelaInsights {
  periodo: string;
  alertas: Alerta[];
  resumo: { alta: number; media: number; oportunidade: number; impacto_total: number };
  comparacao: LinhaComparacao[];
}

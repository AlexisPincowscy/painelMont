import { AvisoDemo, Cabecalho, useFiltros } from "../App";
import { Carregando, Erro, Pill } from "../components/base";
import { useApi } from "../lib/api";
import { pct } from "../lib/format";
import type { Status } from "../lib/types";

/**
 * TELA 6 — Saúde dos Dados.
 *
 * Adição própria à estrutura mínima da seção 4, e a única tela do painel
 * voltada para a GESTÃO, não para a liderança executiva. Por isso ela fica
 * separada no menu: o CEO não precisa dela, quem cuida da operação precisa.
 *
 * É o que transforma a lista de dados faltantes da seção 13 em melhoria
 * contínua, em vez de uma queixa que ficou num slide.
 */

interface CelulaEmpresa {
  empresa: string;
  nome: string;
  cor: string;
  aplicavel: boolean;
  taxa: number | null;
  status: Status;
  preenchidos: number;
  total: number;
  inexistente?: boolean;
  estrutural?: boolean;
  amostra_pequena?: boolean;
}

interface LinhaCompletude {
  campo: string;
  momento: string;
  por_que: string;
  escopo: string;
  kpis_dependentes: { slug: string; nome: string }[];
  por_empresa: CelulaEmpresa[];
  pior_taxa: number | null;
  critico: boolean;
}

interface TelaSaude {
  periodo: string;
  janela: { dias: number; inicio: string; fim: string };
  amostra_minima: number;
  indice_geral: number | null;
  status_geral: Status;
  campos_criticos: number;
  kpis_bloqueados: { empresa: string; cor: string; kpi: string; slug: string; motivo: string }[];
  completude: LinhaCompletude[];
  responsaveis: {
    responsavel: string;
    ativo: boolean;
    empresa: string;
    cor: string;
    motivo_perda: number | null;
    interacao: number | null;
    geral: number;
    status: Status;
    oportunidades: number;
  }[];
  limiares: { bom: number; atencao: number };
}

export default function SaudeDados() {
  const f = useFiltros();
  const { dados, demo, carregando, erro } = useApi<TelaSaude>(
    `/api/saude-dados?periodo=${f.periodo}`,
  );

  return (
    <>
      <Cabecalho
        titulo="Saúde dos Dados"
        pergunta="Em que eu posso confiar — e o que precisa ser corrigido no registro?"
        comEmpresa={false}
      />
      <AvisoDemo ativo={demo} />
      <div className="conteudo">
        {erro && <Erro msg={erro} />}
        {carregando && <Carregando />}
        {dados && <Conteudo d={dados} />}
      </div>
    </>
  );
}

function Celula({ c, minimo }: { c: CelulaEmpresa; minimo: number }) {
  if (!c.aplicavel) {
    return <td className="num" style={{ color: "var(--line)" }}>—</td>;
  }
  // Verificação estrutural: existe ou não existe. Não há percentual a mostrar —
  // e inventar um daria a impressão de uma medição que não foi feita.
  if (c.estrutural || c.inexistente) {
    return (
      <td className="num">
        <span className={`pill ${c.inexistente ? "vermelho" : "verde"}`}>
          {c.inexistente ? "campo inexistente" : "campo existe"}
        </span>
      </td>
    );
  }
  const cor =
    c.status === "verde"
      ? "var(--ok)"
      : c.status === "amarelo"
        ? "var(--warn)"
        : c.status === "vermelho"
          ? "var(--risk)"
          : "var(--muted)";
  return (
    <td
      className="num"
      title={
        c.amostra_pequena
          ? `Amostra de ${c.total} registros — abaixo do mínimo de ${minimo} para colorir o semáforo.`
          : `${c.preenchidos} de ${c.total} registros preenchidos`
      }
    >
      <span style={{ color: cor, fontWeight: 700 }}>{pct(c.taxa, 0)}</span>
      <span style={{ color: "var(--muted)", fontSize: 11, marginLeft: 5 }}>n={c.total}</span>
      {c.amostra_pequena && <sup style={{ color: "var(--warn)" }}> amostra baixa</sup>}
    </td>
  );
}

function Conteudo({ d }: { d: TelaSaude }) {
  const empresas = d.completude[0]?.por_empresa ?? [];

  return (
    <>
      <div className="nota">
        Esta tela é a única do painel voltada para a <strong>gestão</strong>, não para a leitura
        executiva. Ela mede se os campos que sustentam os indicadores estão sendo registrados — e
        nomeia quais KPIs ficam impossíveis quando não estão. É o que transforma a lista de dados
        faltantes em acompanhamento, em vez de uma queixa em slide.
      </div>

      <section className="secao">
        <h3>
          Índice de completude{" "}
          <em>
            · janela móvel de {d.janela.dias} dias ({d.janela.inicio} a {d.janela.fim})
          </em>
        </h3>
        <div className="grade g4">
          <div className="card kpi">
            <div className="topo-kpi">
              <span className="nome">Completude geral dos campos críticos</span>
              <Pill status={d.status_geral} />
            </div>
            <div
              className="valor"
              style={{
                color:
                  d.status_geral === "verde"
                    ? "var(--ok)"
                    : d.status_geral === "amarelo"
                      ? "var(--warn)"
                      : "var(--risk)",
              }}
            >
              {pct(d.indice_geral, 0)}
            </div>
            <span className="det">média das piores taxas por campo</span>
          </div>
          <div className="card kpi">
            <span className="nome">Campos em situação crítica</span>
            <div className="valor" style={{ color: "var(--risk)" }}>
              {d.campos_criticos}
            </div>
            <span className="det">abaixo de {pct(d.limiares.atencao, 0)} ou inexistentes</span>
          </div>
          <div className="card kpi">
            <span className="nome">KPIs bloqueados hoje</span>
            <div className="valor" style={{ color: "var(--warn)" }}>
              {d.kpis_bloqueados.length}
            </div>
            <span className="det">exibidos em cinza na tela da empresa</span>
          </div>
          <div className="card kpi">
            <span className="nome">Responsáveis abaixo do limiar</span>
            <div className="valor">
              {d.responsaveis.filter((r) => r.geral < d.limiares.atencao).length}
              <span style={{ fontSize: 15, color: "var(--muted)" }}> / {d.responsaveis.length}</span>
            </div>
            <span className="det">completude de registro individual</span>
          </div>
        </div>
      </section>

      <section className="secao">
        <h3>
          Completude por campo <em>· fila de trabalho, pior primeiro</em>
        </h3>
        <div className="tbl-wrap">
          <table>
            <thead>
              <tr>
                <th style={{ width: "22%" }}>Campo</th>
                <th style={{ width: "20%" }}>Momento do registro</th>
                {empresas.map((e) => (
                  <th key={e.empresa} className="num">
                    {e.nome}
                  </th>
                ))}
                <th>KPIs que dependem dele</th>
              </tr>
            </thead>
            <tbody>
              {d.completude.map((l) => (
                <tr key={l.campo}>
                  <td className="forte" style={{ fontFamily: "var(--f-mono)", fontSize: 11.5 }}>
                    {l.critico && <span style={{ color: "var(--risk)", marginRight: 5 }}>●</span>}
                    {l.campo}
                    {l.escopo !== "todas" && (
                      <div style={{ fontFamily: "var(--f-display)", fontSize: 10.5, color: "var(--muted)", marginTop: 2 }}>
                        só {l.escopo}
                      </div>
                    )}
                  </td>
                  <td style={{ fontSize: 12 }}>{l.momento}</td>
                  {l.por_empresa.map((c) => (
                    <Celula key={c.empresa} c={c} minimo={d.amostra_minima} />
                  ))}
                  <td style={{ fontSize: 11.5 }}>
                    {l.kpis_dependentes.map((k) => k.nome).join(" · ")}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="nota">
          O <strong>n</strong> ao lado de cada percentual é o tamanho da amostra. Abaixo de{" "}
          {d.amostra_minima} registros a célula fica cinza: um percentual sobre cinco casos não
          merece a autoridade de um semáforo. Completude é métrica de higiene, não de período — por
          isso a janela é móvel de {d.janela.dias} dias.
        </div>
      </section>

      <section className="secao">
        <h3>Por que cada campo importa</h3>
        <div className="grade g2">
          {d.completude
            .filter((l) => l.critico)
            .map((l) => (
              <div className="card" key={l.campo} style={{ borderLeft: "3px solid var(--risk)" }}>
                <h4 style={{ margin: "0 0 6px", fontFamily: "var(--f-mono)", fontSize: 12.5, color: "var(--ink)" }}>
                  {l.campo}
                </h4>
                <p style={{ margin: "0 0 8px", fontSize: 13, color: "var(--ink-2)", lineHeight: 1.5, fontFamily: "var(--f-body)" }}>
                  {l.por_que}
                </p>
                <div style={{ fontSize: 11.5, color: "var(--muted)" }}>
                  <strong style={{ color: "var(--accent)" }}>Registrar em:</strong> {l.momento}
                </div>
              </div>
            ))}
        </div>
      </section>

      {d.kpis_bloqueados.length > 0 && (
        <section className="secao">
          <h3>
            KPIs que o painel declara como não calculáveis{" "}
            <em>· a lista sai da própria camada semântica, não é mantida à mão</em>
          </h3>
          <div className="grade g2">
            {d.kpis_bloqueados.map((b) => (
              <div className="card" key={b.slug} style={{ background: "var(--warn-soft)", borderColor: "var(--warn)" }}>
                <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 7 }}>
                  <span style={{ background: b.cor, width: 4, height: 16, borderRadius: 2 }} />
                  <strong style={{ fontSize: 14 }}>{b.kpi}</strong>
                  <span className="pill cinza">{b.empresa}</span>
                </div>
                <p style={{ margin: 0, fontSize: 13, color: "var(--ink-2)", fontFamily: "var(--f-body)", lineHeight: 1.5 }}>
                  {b.motivo}
                </p>
              </div>
            ))}
          </div>
          <div className="nota">
            Quando um número não pode ser calculado com honestidade, o painel <strong>diz isso</strong>{" "}
            e nomeia o campo que falta — em vez de estimar. Um card cinza é infinitamente mais útil a
            um gestor do que um número plausível e errado.
          </div>
        </section>
      )}

      <section className="secao">
        <h3>
          Registro por responsável <em>· pior primeiro</em>
        </h3>
        <div className="tbl-wrap">
          <table>
            <thead>
              <tr>
                <th>Responsável</th>
                <th>Empresa</th>
                <th className="num">Motivo de perda</th>
                <th className="num">Última interação</th>
                <th className="num">Completude geral</th>
                <th className="num">Oportunidades</th>
              </tr>
            </thead>
            <tbody>
              {d.responsaveis.map((r) => (
                <tr key={`${r.empresa}-${r.responsavel}`}>
                  <td className="forte" style={{ borderLeft: `3px solid ${r.cor}` }}>
                    {r.responsavel}{" "}
                    {!r.ativo && <span className="pill cinza">inativo</span>}
                  </td>
                  <td style={{ fontSize: 12 }}>{r.empresa}</td>
                  <td className="num">{pct(r.motivo_perda, 0)}</td>
                  <td className="num">{pct(r.interacao, 0)}</td>
                  <td className="num">
                    <span
                      style={{
                        color:
                          r.status === "verde"
                            ? "var(--ok)"
                            : r.status === "amarelo"
                              ? "var(--warn)"
                              : "var(--risk)",
                        fontWeight: 700,
                      }}
                    >
                      {pct(r.geral, 0)}
                    </span>
                  </td>
                  <td className="num">{r.oportunidades}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="nota">
          Completude de dado não é problema de sistema, é problema de rotina. Sem nome, ninguém
          corrige; com nome, vira acompanhamento de gestão — e é exatamente por isso que esta tela
          fica <strong>fora do menu executivo</strong>. Ela serve para melhorar o registro, não para
          ranquear pessoas na frente do CEO.
        </div>
      </section>
    </>
  );
}

import { AvisoDemo, Cabecalho, useFiltros } from "../App";
import { Carregando, Erro, Funil, Kpi } from "../components/base";
import { useApi } from "../lib/api";
import { dinheiro, pct } from "../lib/format";
import type { TelaComercial } from "../lib/types";

/**
 * TELA 2 — Comercial.
 *
 * As etapas NÃO são iguais nas três empresas, e não deveriam ser. O que torna
 * a comparação possível é a tabela de tradução: cada empresa mostra o nome real
 * do seu estágio (Cotação, Diagnóstico financeiro, Reunião + diagnóstico) e o
 * grupo lê tudo pelos códigos S1..S6.
 */
export default function Comercial() {
  const f = useFiltros();
  const { dados, demo, carregando, erro } = useApi<TelaComercial>(`/api/comercial?${f.query()}`);

  return (
    <>
      <Cabecalho titulo="Comercial" pergunta="Estamos transformando oportunidades em negócios?" />
      <AvisoDemo ativo={demo} />
      <div className="conteudo">
        {erro && <Erro msg={erro} />}
        {carregando && <Carregando n={3} />}
        {dados && <Conteudo d={dados} />}
      </div>
    </>
  );
}

function Conteudo({ d }: { d: TelaComercial }) {
  const piorPorEmpresa = Object.fromEntries(d.gargalos.map((g) => [g.empresa, g.estagio]));

  return (
    <>
      <section className="secao">
        <h3>Eficiência comercial consolidada</h3>
        <div className="grade g3">
          {d.kpis.map((m) => (
            <Kpi key={m.slug} m={m} compacto />
          ))}
        </div>
      </section>

      {/* --- onde vaza, em reais --- */}
      <section className="secao">
        <h3>
          Onde o funil vaza <em>· traduzido em reais, para permitir priorizar entre empresas</em>
        </h3>
        <div className="tbl-wrap">
          <table>
            <thead>
              <tr>
                <th>Empresa</th>
                <th>Passagem com maior perda</th>
                <th className="num">Conversão</th>
                <th className="num">Oportunidades perdidas</th>
                <th className="num">Impacto estimado</th>
              </tr>
            </thead>
            <tbody>
              {d.gargalos.map((g) => (
                <tr key={g.empresa}>
                  <td className="forte" style={{ borderLeft: `3px solid ${g.cor}` }}>
                    {g.nome}
                  </td>
                  <td>
                    {g.rotulo_anterior} → <strong>{g.rotulo}</strong>
                  </td>
                  <td className="num">{pct(g.conversao_da_anterior)}</td>
                  <td className="num">{g.perda}</td>
                  <td className="num forte">{dinheiro(g.impacto_estimado)}</td>
                </tr>
              ))}
              {!d.gargalos.length && (
                <tr>
                  <td colSpan={5} className="vazio">
                    Sem coorte suficiente no período para localizar gargalo.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
        <div className="nota">
          Percentual sozinho não permite priorizar entre operações com tickets diferentes. Uma queda
          de 22% na Montseguro e uma de 8% na Prop5 não são comparáveis em percentual —{" "}
          <strong>são em impacto financeiro</strong>.
        </div>
      </section>

      {/* --- funis lado a lado --- */}
      <section className="secao">
        <h3>
          Funis por empresa <em>· cada uma com os seus próprios estágios</em>
        </h3>
        <div className="grade g3">
          {d.funis.map((f) => (
            <div className="card" key={f.empresa}>
              <header style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 12 }}>
                <span className="barra-co" style={{ background: f.cor, width: 4, height: 18, borderRadius: 2 }} />
                <h4 style={{ margin: 0, fontSize: 14, fontWeight: 700 }}>{f.nome}</h4>
              </header>
              <Funil etapas={f.etapas} cor={f.cor} destaque={piorPorEmpresa[f.empresa]} />
              <div className="nota" style={{ marginTop: 11 }}>
                Coorte de {f.coorte} oportunidades · <strong>{pct(f.maturidade, 0)} já percorreu o
                ciclo esperado</strong>. Conversão de coorte imatura parece uma queda que não existe.
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* --- pipeline --- */}
      <section className="secao">
        <h3>
          Pipeline por estágio <em>· bruto × ponderado pela probabilidade observada</em>
        </h3>
        <div className="grade g3">
          {d.pipelines.map((p) => (
            <div className="card" key={p.empresa}>
              <header style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 10 }}>
                <span style={{ background: p.cor, width: 4, height: 18, borderRadius: 2 }} />
                <h4 style={{ margin: 0, fontSize: 14, fontWeight: 700 }}>{p.nome}</h4>
              </header>
              <div className="minitab" style={{ marginBottom: 10 }}>
                <div>
                  <span className="k">Ponderado</span>
                  <span className="v">{dinheiro(p.ponderado, true)}</span>
                </div>
                <div>
                  <span className="k">Cobertura da meta</span>
                  <span className="v">{p.cobertura ? `${p.cobertura.toFixed(1)}×` : "—"}</span>
                </div>
                <div>
                  <span className="k">Aging</span>
                  <span className="v">{pct(p.aging, 0)}</span>
                </div>
                <div>
                  <span className="k">Bruto</span>
                  <span className="v">{dinheiro(p.bruto, true)}</span>
                </div>
              </div>
              <div className="tbl-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Estágio</th>
                      <th className="num">Qtd</th>
                      <th className="num">Prob.</th>
                      <th className="num">Ponderado</th>
                    </tr>
                  </thead>
                  <tbody>
                    {p.por_estagio.map((e) => (
                      <tr key={e.estagio}>
                        <td>{e.rotulo}</td>
                        <td className="num">{e.qtd}</td>
                        <td className="num">{pct(e.probabilidade, 0)}</td>
                        <td className="num">{dinheiro(e.ponderado, true)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          ))}
        </div>
        <div className="nota">
          As probabilidades <strong>não são arbitradas</strong>: são a taxa de conversão observada de
          cada estágio até o fechamento, calculada sobre o histórico de cada empresa. Valores fixos
          só são usados enquanto a amostra é menor que 30.
        </div>
      </section>

      {/* --- ciclo e produtividade --- */}
      <section className="secao">
        <h3>Ciclo médio e produtividade comercial</h3>
        <div className="grade g2">
          <div className="card">
            <div className="tbl-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Empresa</th>
                    <th className="num">Ciclo do período</th>
                    <th className="num">Período anterior</th>
                    <th className="num">Esperado</th>
                  </tr>
                </thead>
                <tbody>
                  {d.ciclos.map((c) => (
                    <tr key={c.empresa}>
                      <td className="forte" style={{ borderLeft: `3px solid ${c.cor}` }}>
                        {c.nome}
                      </td>
                      <td className="num">{c.ciclo ? `${Math.round(c.ciclo)} d` : "—"}</td>
                      <td className="num">{c.ciclo_anterior ? `${Math.round(c.ciclo_anterior)} d` : "—"}</td>
                      <td className="num">{c.esperado} d</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="nota" style={{ marginTop: 10 }}>
              Mediana, não média: um negócio atípico de ciclo muito longo não deve mover a leitura do
              time. Comparar o ciclo da Prop5 com o da Montseguro não faz sentido — são decisões de
              natureza diferente.
            </div>
          </div>
          <div className="card">
            <div className="tbl-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Responsável</th>
                    <th className="num">Receita</th>
                    <th className="num">Oport.</th>
                    <th className="num">Conversão</th>
                  </tr>
                </thead>
                <tbody>
                  {d.rankings.flatMap((r) =>
                    r.linhas.slice(0, 4).map((l) => (
                      <tr key={`${r.empresa}-${l.nome}`}>
                        <td className="forte" style={{ borderLeft: `3px solid ${r.cor}` }}>
                          {l.nome} {!l.ativo && <span className="pill cinza">inativo</span>}
                        </td>
                        <td className="num">{dinheiro(l.receita, true)}</td>
                        <td className="num">{l.oportunidades}</td>
                        <td className="num">{pct(l.conversao, 0)}</td>
                      </tr>
                    )),
                  )}
                </tbody>
              </table>
            </div>
            <div className="nota" style={{ marginTop: 10 }}>
              Responsáveis desligados continuam na lista marcados como inativos. Apagá-los apagaria
              o histórico de produtividade do período em que produziram.
            </div>
          </div>
        </div>
      </section>
    </>
  );
}

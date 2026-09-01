import { useState } from "react";
import { AvisoDemo, Cabecalho, useFiltros } from "../App";
import { CardAlerta, Carregando, Erro, Pill } from "../components/base";
import { useApi } from "../lib/api";
import { dinheiro, pct } from "../lib/format";
import type { TelaInsights } from "../lib/types";

/**
 * TELA 5 — Insights.
 *
 * Nove regras rodam a cada atualização. A tela do CEO mostra as cinco mais
 * severas; aqui aparecem todas, com filtro por camada e por severidade.
 *
 * Nenhum alerta afirma a CAUSA. Ele aponta onde olhar e propõe uma hipótese de
 * investigação — inventar explicação que o dado não sustenta é o jeito mais
 * rápido de perder a confiança da liderança.
 */
export default function Insights() {
  const f = useFiltros();
  const { dados, demo, carregando, erro } = useApi<TelaInsights>(`/api/insights?periodo=${f.periodo}`);
  const [severidade, setSeveridade] = useState("");
  const [camada, setCamada] = useState("");

  const alertas = (dados?.alertas ?? []).filter(
    (a) => (!severidade || a.severidade === severidade) && (!camada || a.camada === camada),
  );
  const camadas = [...new Set((dados?.alertas ?? []).map((a) => a.camada))];

  return (
    <>
      <Cabecalho titulo="Insights" pergunta="O que eu ainda não vi?" comEmpresa={false} />
      <AvisoDemo ativo={demo} />
      <div className="conteudo">
        {erro && <Erro msg={erro} />}
        {carregando && <Carregando />}
        {dados && (
          <>
            <section className="secao">
              <h3>Resumo do período</h3>
              <div className="grade g4">
                <div className="card kpi">
                  <span className="nome">Severidade alta</span>
                  <div className="valor" style={{ color: "var(--risk)" }}>
                    {dados.resumo.alta}
                  </div>
                  <span className="det">exigem decisão nesta semana</span>
                </div>
                <div className="card kpi">
                  <span className="nome">Severidade média</span>
                  <div className="valor" style={{ color: "var(--warn)" }}>
                    {dados.resumo.media}
                  </div>
                  <span className="det">acompanhamento próximo</span>
                </div>
                <div className="card kpi">
                  <span className="nome">Oportunidades</span>
                  <div className="valor" style={{ color: "var(--ok)" }}>
                    {dados.resumo.oportunidade}
                  </div>
                  <span className="det">onde acelerar, não onde apagar incêndio</span>
                </div>
                <div className="card kpi">
                  <span className="nome">Impacto financeiro somado</span>
                  <div className="valor">{dinheiro(dados.resumo.impacto_total, true)}</div>
                  <span className="det">estimativa dos alertas de risco</span>
                </div>
              </div>
            </section>

            <section className="secao">
              <h3>
                Fila de alertas <em>· ordenada por impacto × urgência × confiança</em>
              </h3>
              <div className="filtros" style={{ marginBottom: 4 }}>
                <label htmlFor="f-sev">Severidade</label>
                <select id="f-sev" value={severidade} onChange={(e) => setSeveridade(e.target.value)}>
                  <option value="">Todas</option>
                  <option value="alta">Alta</option>
                  <option value="media">Média</option>
                  <option value="oportunidade">Oportunidade</option>
                </select>
                <label htmlFor="f-cam">Camada</label>
                <select id="f-cam" value={camada} onChange={(e) => setCamada(e.target.value)}>
                  <option value="">Todas</option>
                  {camadas.map((c) => (
                    <option key={c} value={c}>
                      {c}
                    </option>
                  ))}
                </select>
              </div>
              <div className="grade g2">
                {alertas.map((a) => (
                  <CardAlerta a={a} key={`${a.regra}-${a.empresa}-${a.titulo}`} />
                ))}
              </div>
              {!alertas.length && <div className="vazio">Nenhum alerta com estes filtros.</div>}
              <div className="nota">
                A ordenação é <strong>impacto em reais × urgência × confiança</strong>. A confiança cai
                quando a amostra é pequena — é o que impede que uma queda de 50% em quatro leads
                apareça acima de um problema real de duzentos mil reais.
              </div>
            </section>

            <section className="secao">
              <h3>Comparação normalizada entre empresas</h3>
              <div className="tbl-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Empresa</th>
                      <th>Status</th>
                      <th className="num">Atingimento</th>
                      <th className="num">Conversão</th>
                      <th className="num">Realização</th>
                      <th className="num">CAC</th>
                      <th className="num">Cobertura</th>
                      <th className="num">Crescimento</th>
                    </tr>
                  </thead>
                  <tbody>
                    {dados.comparacao.map((l) => (
                      <tr key={l.empresa}>
                        <td className="forte" style={{ borderLeft: `3px solid ${l.cor}` }}>
                          {l.nome}
                        </td>
                        <td>
                          <Pill status={l.status} />
                        </td>
                        <td className="num">
                          {l.atingimento_ritmo ? `${l.atingimento_ritmo.toFixed(2)}×` : "—"}
                        </td>
                        <td
                          className="num"
                          title={
                            (l.maturidade_coorte ?? 1) < 0.5
                              ? "Coorte do período ainda imatura — a conversão real será maior."
                              : undefined
                          }
                          style={{
                            color: (l.maturidade_coorte ?? 1) < 0.5 ? "var(--muted)" : undefined,
                          }}
                        >
                          {pct(l.conv_s1_s6)}
                          {(l.maturidade_coorte ?? 1) < 0.5 && (
                            <sup style={{ color: "var(--warn)" }}> imatura</sup>
                          )}
                        </td>
                        <td className="num">{pct(l.taxa_realizacao)}</td>
                        <td className="num">{dinheiro(l.cac)}</td>
                        <td className="num">
                          {l.cobertura_pipeline ? `${l.cobertura_pipeline.toFixed(1)}×` : "—"}
                        </td>
                        <td className="num">{pct(l.crescimento)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          </>
        )}
      </div>
    </>
  );
}

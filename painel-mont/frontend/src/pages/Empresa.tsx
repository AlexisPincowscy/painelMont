import { useParams } from "react-router-dom";
import { AvisoDemo, Cabecalho, useFiltros } from "../App";
import { Carregando, Erro, Funil, Kpi, Medidor, Pill } from "../components/base";
import { useApi } from "../lib/api";
import { dinheiro, pct } from "../lib/format";
import type { TelaEmpresa } from "../lib/types";

/**
 * TELA 4 — Visão individual por empresa.
 *
 * O briefing rejeita explicitamente "os mesmos indicadores copiados para as três
 * operações". Cada empresa recebe da API um conjunto DIFERENTE de KPIs — e os
 * conjuntos não têm interseção (há teste automatizado garantindo isso).
 */
export default function EmpresaPage() {
  const { slug } = useParams();
  const f = useFiltros();
  const { dados, demo, carregando, erro } = useApi<TelaEmpresa>(
    `/api/empresas/${slug}?periodo=${f.periodo}`,
  );

  return (
    <>
      <Cabecalho
        titulo={dados?.empresa.nome ?? "Empresa"}
        pergunta={dados?.empresa.descricao ?? "O que está acontecendo aqui dentro?"}
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

function Conteudo({ d }: { d: TelaEmpresa }) {
  const cor = d.empresa.cor;
  return (
    <>
      <section className="secao">
        <h3>
          Ritmo em relação à meta{" "}
          <em>
            · peso do ritmo no forecast desta empresa: {d.empresa.peso_forecast_ritmo?.toFixed(2)}
          </em>
        </h3>
        <div className="grade g21">
          <div className="card empresa-card">
            <header>
              <span className="barra-co" style={{ background: cor }} />
              <h4>{d.empresa.nome}</h4>
              <Pill status={d.ritmo.status} />
            </header>
            <Medidor r={d.ritmo} />
            <div className="minitab">
              <div>
                <span className="k">Projeção de fechamento</span>
                <span className="v">{dinheiro(d.ritmo.forecast, true)}</span>
              </div>
              <div>
                <span className="k">Gap do ritmo</span>
                <span className="v" style={{ color: (d.ritmo.gap ?? 0) < 0 ? "var(--risk)" : "var(--ok)" }}>
                  {dinheiro(d.ritmo.gap, true)}
                </span>
              </div>
              <div>
                <span className="k">Necessidade diária</span>
                <span className="v">{dinheiro(d.ritmo.necessidade_diaria, true)}</span>
              </div>
              <div>
                <span className="k">Índice de esforço</span>
                <span className="v">
                  {d.ritmo.indice_esforco ? `${d.ritmo.indice_esforco.toFixed(2)}×` : "—"}
                </span>
              </div>
            </div>
            <div className="nota">
              Faltam <strong>{d.ritmo.dias_uteis_totais - d.ritmo.dias_uteis_decorridos} dias úteis</strong>{" "}
              no período. O peso do ritmo no forecast é {d.empresa.peso_forecast_ritmo?.toFixed(2)} porque
              esta operação tem ciclo esperado de {d.empresa.ciclo_esperado_dias} dias — quanto mais
              longo o ciclo, mais o funil prevê melhor que a média diária.
            </div>
          </div>

          <div className="card">
            <h4 style={{ margin: "0 0 10px", fontSize: 14, fontWeight: 700 }}>Funil próprio</h4>
            <Funil etapas={d.funil.etapas} cor={cor} />
            <div className="nota" style={{ marginTop: 11 }}>
              Coorte de {d.funil.coorte} oportunidades criadas no período ·{" "}
              <strong>{pct(d.funil.maturidade, 0)}</strong> já percorreu o ciclo esperado.
            </div>
          </div>
        </div>
      </section>

      <section className="secao">
        <h3>
          Indicadores próprios da {d.empresa.nome}{" "}
          <em>· unidade de valor: {d.empresa.unidade_valor}</em>
        </h3>
        <div className="grade g4">
          {d.kpis.map((m) => (
            <Kpi key={m.slug} m={m} compacto />
          ))}
        </div>
        <div className="nota">
          Nenhum destes indicadores aparece nas outras duas empresas. Repetir os mesmos KPIs nas três
          operações seria tratá-las como se ganhassem dinheiro do mesmo jeito — e elas não ganham.
        </div>
      </section>

      <section className="secao">
        <h3>
          Probabilidade de fechamento por estágio <em>· calibrada com o histórico desta empresa</em>
        </h3>
        <div className="tbl-wrap">
          <table>
            <thead>
              <tr>
                <th>Estágio canônico</th>
                <th>Nome nesta empresa</th>
                <th className="num">Prob. de chegar ao fechamento</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(d.probabilidades).map(([est, prob]) => {
                const etapa = d.funil.etapas.find((e) => e.estagio === est);
                return (
                  <tr key={est}>
                    <td className="forte">{est}</td>
                    <td>{etapa?.rotulo ?? "—"}</td>
                    <td className="num">{pct(prob, 1)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        <div className="nota">
          Estes números <strong>não são arbitrados</strong>. São a conversão observada de cada
          estágio até o fechamento, recalculada a cada leitura. Valores fixos de partida só
          permanecem enquanto a amostra do estágio for menor que 30 — chutar é aceitável no dia 1,
          continuar chutando com dado na mesa não é.
        </div>
      </section>
    </>
  );
}

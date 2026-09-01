import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { AvisoDemo, Cabecalho, useFiltros } from "../App";
import { Carregando, Erro, Kpi } from "../components/base";
import { useApi } from "../lib/api";
import { dinheiro, pct, rotuloMes } from "../lib/format";
import type { TelaMarketing } from "../lib/types";

/**
 * TELA 3 — Marketing.
 *
 * Existe para responder UMA pergunta: onde colocar o próximo real.
 *
 * A decisão analítica mais importante desta tela é a atribuição por COORTE DE
 * ENTRADA DO LEAD. Dividir a receita de agosto pelo investimento de agosto faz
 * um mês de corte de verba parecer o mais eficiente da história — e leva a
 * cortar mais.
 */
export default function Marketing() {
  const f = useFiltros();
  const { dados, demo, carregando, erro } = useApi<TelaMarketing>(`/api/marketing?${f.query()}`);

  return (
    <>
      <Cabecalho titulo="Marketing" pergunta="Onde colocar o próximo real?" />
      <AvisoDemo ativo={demo} />
      <div className="conteudo">
        {erro && <Erro msg={erro} />}
        {carregando && <Carregando />}
        {dados && <Conteudo d={dados} />}
      </div>
    </>
  );
}

function Conteudo({ d }: { d: TelaMarketing }) {
  const coortes = d.coortes.map((c) => ({
    mes: rotuloMes(c.coorte),
    "30 dias": c.roas_30,
    "60 dias": c.roas_60,
    "90 dias": c.roas_90,
  }));
  const madura = d.canais[0]?.coorte_madura ?? false;

  return (
    <>
      <section className="secao">
        <h3>Eficiência de aquisição</h3>
        <div className="grade g4">
          {d.kpis.map((m) => (
            <Kpi key={m.slug} m={m} compacto />
          ))}
        </div>
      </section>

      {/* --- cascata --- */}
      <section className="secao">
        <h3>
          Do investimento à receita <em>· com a taxa de passagem entre cada par</em>
        </h3>
        <div className="grade" style={{ gridTemplateColumns: `repeat(${d.cascata.length}, 1fr)` }}>
          {d.cascata.map((e) => (
            <div className="card" key={e.rotulo}>
              <span className="k" style={{ fontFamily: "var(--f-mono)", fontSize: 9, letterSpacing: ".1em", textTransform: "uppercase", color: "var(--muted)" }}>
                {e.rotulo}
              </span>
              <div style={{ fontSize: 21, fontWeight: 700, letterSpacing: "-.03em", marginTop: 4 }}>
                {e.unidade === "BRL" ? dinheiro(e.valor, true) : e.valor.toLocaleString("pt-BR")}
              </div>
              {e.passagem !== null && (
                <div style={{ fontFamily: "var(--f-mono)", fontSize: 11, color: "var(--accent)" }}>
                  ↳ {pct(e.passagem, 0)} da etapa anterior
                </div>
              )}
            </div>
          ))}
        </div>
      </section>

      {/* --- matriz de canais --- */}
      <section className="secao">
        <h3>
          Matriz de canais <em>· volume × custo × retorno</em>
        </h3>
        <div className="tbl-wrap">
          <table>
            <thead>
              <tr>
                <th>Canal</th>
                <th className="num">Verba</th>
                <th className="num">% da verba</th>
                <th className="num">Leads</th>
                <th className="num">CPL</th>
                <th className="num">CPL qualif.</th>
                <th className="num">Aproveit.</th>
                <th className="num">CAC</th>
                <th className="num">ROAS coorte 90d</th>
                <th className="num">ROAS de caixa</th>
              </tr>
            </thead>
            <tbody>
              {d.canais.map((c) => (
                <tr key={c.slug}>
                  <td className="forte">
                    {c.canal}{" "}
                    {c.sem_investimento_direto && <span className="pill cinza">sem verba direta</span>}
                  </td>
                  <td className="num">{c.investimento ? dinheiro(c.investimento, true) : "—"}</td>
                  <td className="num">{c.investimento ? pct(c.participacao_verba, 0) : "—"}</td>
                  <td className="num">{c.leads}</td>
                  <td className="num">{dinheiro(c.cpl)}</td>
                  <td className="num">{dinheiro(c.cpl_qualificado)}</td>
                  <td className="num">{pct(c.aproveitamento, 0)}</td>
                  <td className="num">{dinheiro(c.cac)}</td>
                  <td
                    className="num forte"
                    title={
                      c.coorte_madura
                        ? undefined
                        : "Coorte ainda imatura: menos de 90 dias desde a entrada dos leads."
                    }
                    style={{
                      color: !c.coorte_madura
                        ? "var(--muted)"
                        : c.roas === null
                          ? "var(--muted)"
                          : c.roas >= 3
                            ? "var(--ok)"
                            : c.roas >= 1
                              ? "var(--warn)"
                              : "var(--risk)",
                      fontWeight: c.coorte_madura ? 600 : 400,
                    }}
                  >
                    {c.roas !== null ? `${c.roas.toFixed(2)}×` : "—"}
                    {!c.coorte_madura && <sup style={{ color: "var(--warn)" }}> imatura</sup>}
                  </td>
                  <td className="num" style={{ color: "var(--muted)" }}>
                    {c.roas_caixa !== null ? `${c.roas_caixa.toFixed(2)}×` : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="nota">
          <strong>Dois ROAS, de propósito.</strong> O “de caixa” divide a receita reconhecida no mês
          pelo investimento do mês — é o que a maioria dos painéis chama de ROAS, e ele infla porque
          mistura receita recorrente de safras antigas com verba nova. O <strong>ROAS de coorte</strong>{" "}
          mede a receita gerada pelos leads que entraram no período, até 90 dias depois. É ele que
          decide realocação de verba.
        </div>

        {!madura && (
          <div className="nota warn">
            A coorte deste período <strong>ainda não maturou</strong> (menos de 90 dias desde a
            entrada dos leads). O ROAS de coorte aparece baixo por imaturidade, não por
            ineficiência — para decidir corte de verba, use uma coorte de pelo menos três meses
            atrás.
          </div>
        )}

        {d.canais.some((c) => c.sem_investimento_direto) && (
          <div className="nota">
            Canais orgânicos e de indicação não têm investimento direto. O painel diz isso em vez de
            ratear a verba entre eles — <strong>ratear seria inventar dado</strong>, e um CAC
            inventado é pior que um CAC ausente.
          </div>
        )}
      </section>

      {/* --- maturação --- */}
      <section className="secao">
        <h3>
          Maturação das coortes <em>· o retorno de cada safra de leads em 30, 60 e 90 dias</em>
        </h3>
        <div className="card" style={{ height: 280 }}>
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={coortes} margin={{ top: 8, right: 12, left: 4, bottom: 4 }}>
              <CartesianGrid stroke="var(--line-soft)" vertical={false} />
              <XAxis dataKey="mes" tick={{ fontSize: 11, fill: "var(--muted)" }} tickLine={false} axisLine={false} />
              <YAxis
                tick={{ fontSize: 11, fill: "var(--muted)" }}
                tickLine={false}
                axisLine={false}
                tickFormatter={(v: number) => `${v.toFixed(1)}×`}
                width={48}
              />
              <Tooltip
                formatter={(v: number) => `${Number(v).toFixed(2)}×`}
                contentStyle={{
                  background: "var(--surface)",
                  border: "1px solid var(--line)",
                  borderRadius: 4,
                  fontSize: 12,
                }}
              />
              <Legend wrapperStyle={{ fontSize: 12 }} />
              {/* Paleta neutra: verde/âmbar/vermelho ficam reservados ao semáforo. */}
              <Line type="monotone" dataKey="30 dias" stroke="#9AA6C4" strokeWidth={1.6} dot={false} />
              <Line type="monotone" dataKey="60 dias" stroke="#5A74EE" strokeWidth={1.8} dot={false} />
              <Line type="monotone" dataKey="90 dias" stroke="var(--accent)" strokeWidth={2.4} dot={{ r: 2.5 }} />
            </LineChart>
          </ResponsiveContainer>
        </div>
        <div className="nota">
          A distância entre as três linhas <strong>é o tempo que o negócio leva para converter</strong>.
          Onde elas ficam longe, julgar um canal em 30 dias é injusto; onde ficam próximas, o ciclo é
          curto e a decisão pode ser mais rápida.
        </div>
      </section>
    </>
  );
}

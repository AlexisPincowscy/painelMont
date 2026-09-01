import { Link } from "react-router-dom";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { AvisoDemo, Cabecalho, useFiltros } from "../App";
import { CardAlerta, Carregando, Erro, Kpi, Medidor, Pill } from "../components/base";
import { useApi } from "../lib/api";
import { dinheiro, pct, rotuloMes } from "../lib/format";
import type { Overview } from "../lib/types";

/**
 * TELA 1 — CEO Overview. A regra 5–30–5.
 *
 *   5 segundos  → está tudo bem?      Três semáforos, acima da dobra.
 *   30 segundos → onde está o problema? Ritmo, forecast e até 5 alertas.
 *   5 minutos   → por quê?             Drill-down preservando os filtros.
 *
 * Decisão deliberada: NÃO há um card gigante de "Receita Total do Grupo" no
 * topo. É o número que todo dashboard coloca ali e é justamente o que menos
 * ajuda a decidir onde agir.
 */
export default function Ceo() {
  const f = useFiltros();
  const { dados, demo, carregando, erro } = useApi<Overview>(`/api/overview?periodo=${f.periodo}`);

  return (
    <>
      <Cabecalho
        titulo="CEO Overview"
        pergunta="Está tudo bem? Onde eu ajo primeiro?"
        comEmpresa={false}
      />
      <AvisoDemo ativo={demo} />
      <div className="conteudo">
        {erro && <Erro msg={erro} />}
        {carregando && <Carregando n={3} />}
        {dados && <Conteudo d={dados} />}
      </div>
    </>
  );
}

function Conteudo({ d }: { d: Overview }) {
  const f = useFiltros();
  const serie = d.consolidado.rrg.tendencia.map((v, i, arr) => ({
    mes: rotuloMes(mesDeIndice(d.periodo.rotulo, arr.length - 1 - i)),
    rrg: v,
  }));

  return (
    <>
      {/* --- 5 segundos: os semáforos ocupam a posição mais valiosa da tela --- */}
      <section className="secao">
        <h3>
          Semáforo por empresa <em>· ritmo, esforço e cobertura de pipeline combinados</em>
        </h3>
        <div className="grade g3">
          {d.empresas.map(({ empresa, ritmo, receita, vig }) => (
            <div className="card empresa-card" key={empresa.slug}>
              <header>
                <span className="barra-co" style={{ background: empresa.cor }} />
                <h4>{empresa.nome}</h4>
                <Pill status={ritmo.status} />
              </header>
              <span className="un">unidade de valor: {empresa.unidade_valor}</span>
              <Medidor r={ritmo} />
              <div className="minitab">
                <div>
                  <span className="k">Atingimento do ritmo</span>
                  <span className="v">
                    {ritmo.atingimento_ritmo ? `${ritmo.atingimento_ritmo.toFixed(2)}×` : "—"}
                  </span>
                </div>
                <div>
                  <span className="k">Projeção</span>
                  <span className="v">{dinheiro(ritmo.forecast, true)}</span>
                </div>
                <div>
                  <span className="k">Índice de esforço</span>
                  <span className="v">
                    {ritmo.indice_esforco ? `${ritmo.indice_esforco.toFixed(2)}×` : "—"}
                  </span>
                </div>
                <div>
                  <span className="k">Cobertura pipeline</span>
                  <span className="v">
                    {ritmo.cobertura_pipeline ? `${ritmo.cobertura_pipeline.toFixed(1)}×` : "—"}
                  </span>
                </div>
              </div>
              <div className="nota">
                Receita reconhecida <strong>{dinheiro(receita.valor, true)}</strong> · volume
                intermediado <strong>{dinheiro(vig.valor, true)}</strong>.
                <br />
                As duas grandezas nunca se somam.
              </div>
              <Link to={`/empresas/${empresa.slug}?${f.query()}`} style={{ color: "var(--accent)", fontSize: 12.5, fontWeight: 600 }}>
                Abrir {empresa.nome} →
              </Link>
            </div>
          ))}
        </div>
      </section>

      {/* --- 30 segundos: consolidado e eficiência --- */}
      <section className="secao">
        <h3>
          Consolidado do grupo <em>· {d.periodo.dias_uteis_decorridos} de {d.periodo.dias_uteis_totais} dias úteis decorridos</em>
        </h3>
        <div className="grade g4">
          <Kpi m={d.consolidado.rrg} compacto />
          <Kpi m={d.consolidado.forecast} compacto />
          <Kpi m={d.consolidado.cac} />
          <Kpi m={d.consolidado.conv_s1_s6} />
        </div>
        <div className="grade g3">
          <Kpi m={d.consolidado.vig} compacto />
          <Kpi m={d.consolidado.taxa_realizacao} />
          <Kpi m={d.consolidado.roas} />
        </div>
        <div className="nota warn">
          <strong>RRG e VIG são grandezas diferentes e nunca são somadas.</strong> A Receita
          Reconhecida é o resultado do grupo; o Volume Intermediado mede a escala da operação —
          prêmio anualizado, volume estruturado e valor contratado. Somar os dois inflaria o
          resultado em mais de dez vezes.
        </div>
      </section>

      {/* --- os alertas: no máximo cinco, ordenados por impacto --- */}
      <section className="secao">
        <h3>
          Prioridades de hoje <em>· no máximo cinco — um painel com trinta alertas não tem nenhum</em>
        </h3>
        <div className="grade g2">
          {d.alertas.map((a) => (
            <CardAlerta a={a} key={`${a.regra}-${a.empresa}-${a.titulo}`} />
          ))}
          {!d.alertas.length && <div className="vazio">Nenhum alerta acima do limiar neste período.</div>}
        </div>
      </section>

      {/* --- comparação normalizada --- */}
      <section className="secao">
        <h3>
          Comparação entre empresas <em>· apenas grandezas normalizadas</em>
        </h3>
        <div className="tbl-wrap">
          <table>
            <thead>
              <tr>
                <th>Empresa</th>
                <th>Status</th>
                <th className="num">Atingimento</th>
                <th className="num">Conversão S1→S6</th>
                <th className="num">Realização S6→S7</th>
                <th className="num">Ciclo</th>
                <th className="num">CAC</th>
                <th className="num">Cobertura</th>
                <th className="num">Produtividade</th>
                <th className="num">Crescimento</th>
              </tr>
            </thead>
            <tbody>
              {d.comparacao.map((l) => (
                <tr key={l.empresa}>
                  <td className="forte" style={{ borderLeft: `3px solid ${l.cor}` }}>
                    {l.nome}
                  </td>
                  <td>
                    <Pill status={l.status} />
                  </td>
                  <td className="num">{l.atingimento_ritmo ? `${l.atingimento_ritmo.toFixed(2)}×` : "—"}</td>
                  <td
                    className="num"
                    title={
                      (l.maturidade_coorte ?? 1) < 0.5
                        ? "Coorte do período ainda imatura — a conversão real será maior."
                        : undefined
                    }
                    style={{ color: (l.maturidade_coorte ?? 1) < 0.5 ? "var(--muted)" : undefined }}
                  >
                    {pct(l.conv_s1_s6)}
                    {(l.maturidade_coorte ?? 1) < 0.5 && <sup style={{ color: "var(--warn)" }}> imatura</sup>}
                  </td>
                  <td className="num">{pct(l.taxa_realizacao)}</td>
                  <td className="num">{l.ciclo_medio ? `${Math.round(l.ciclo_medio)} d` : "—"}</td>
                  <td className="num">{dinheiro(l.cac)}</td>
                  <td className="num">{l.cobertura_pipeline ? `${l.cobertura_pipeline.toFixed(1)}×` : "—"}</td>
                  <td className="num">{dinheiro(l.produtividade, true)}</td>
                  <td className="num">{pct(l.crescimento)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="nota">
          Conversões marcadas como <em>imaturas</em> vêm de coortes que ainda não percorreram o
          ciclo do negócio — o número sobe conforme a safra amadurece, e lê-lo como queda seria erro.
          Receita absoluta, ticket médio e volume <strong>não entram nesta comparação</strong>. Uma
          única operação da Prop5 pode superar o mês inteiro da Montseguro sem que isso signifique
          melhor performance — comparabilidade exige normalização.
        </div>
      </section>

      {/* --- evolução --- */}
      <section className="secao">
        <h3>Evolução da receita reconhecida do grupo · 12 meses</h3>
        <div className="card" style={{ height: 260 }}>
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={serie} margin={{ top: 8, right: 8, left: 8, bottom: 4 }}>
              <CartesianGrid stroke="var(--line-soft)" vertical={false} />
              <XAxis dataKey="mes" tick={{ fontSize: 11, fill: "var(--muted)" }} tickLine={false} axisLine={false} />
              <YAxis
                tick={{ fontSize: 11, fill: "var(--muted)" }}
                tickLine={false}
                axisLine={false}
                tickFormatter={(v: number) => dinheiro(v, true)}
                width={70}
              />
              <Tooltip
                formatter={(v: number) => dinheiro(v)}
                contentStyle={{
                  background: "var(--surface)",
                  border: "1px solid var(--line)",
                  borderRadius: 4,
                  fontSize: 12,
                }}
              />
              <Legend wrapperStyle={{ fontSize: 12 }} />
              <Bar dataKey="rrg" name="Receita reconhecida" fill="var(--accent)" radius={[3, 3, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </section>
    </>
  );
}

function mesDeIndice(rotulo: string, atras: number): string {
  const [ano, mes] = rotulo.split("-").map(Number);
  const d = new Date(ano, mes - 1 - atras, 1);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
}

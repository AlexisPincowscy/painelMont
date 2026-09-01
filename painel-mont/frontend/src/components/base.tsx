import { useState } from "react";
import type { Alerta, Metrica, Ritmo, Status } from "../lib/types";
import { corVariacao, dinheiro, fmt, pct, variacao } from "../lib/format";

/* ------------------------------------------------------------- semáforo */
export function Pill({ status, texto }: { status: Status; texto?: string }) {
  return (
    <span className={`pill ${status}`}>
      <span className={`dot ${status}`} />
      {texto ?? status}
    </span>
  );
}

/* --------------------------------------------------------------- sparkline
   Minigráfico de tendência. Existe porque um número sem trajetória não é
   informação — é curiosidade. */
export function Sparkline({ serie, cor = "var(--accent)" }: { serie: number[]; cor?: string }) {
  if (!serie || serie.length < 2) return null;
  const max = Math.max(...serie);
  const min = Math.min(...serie);
  const span = max - min || 1;
  const w = 92;
  const h = 26;
  const pontos = serie.map((v, i) => {
    const x = (i / (serie.length - 1)) * w;
    const y = h - ((v - min) / span) * (h - 4) - 2;
    return [x, y] as const;
  });
  const d = pontos.map(([x, y], i) => `${i ? "L" : "M"}${x.toFixed(1)},${y.toFixed(1)}`).join(" ");
  const area = `${d} L${w},${h} L0,${h} Z`;
  const [ux, uy] = pontos[pontos.length - 1];
  return (
    <svg width={w} height={h} viewBox={`0 0 ${w} ${h}`} role="img" aria-label="tendência de 12 meses">
      <path d={area} fill={cor} opacity="0.1" />
      <path d={d} fill="none" stroke={cor} strokeWidth="1.5" strokeLinejoin="round" />
      <circle cx={ux} cy={uy} r="2.4" fill={cor} />
    </svg>
  );
}

/* --------------------------------------------------------------- KPI card
   Toda métrica chega da API com valor, unidade, status, comparação e a ficha
   do indicador. Este componente NÃO calcula nada — só apresenta. */
export function Kpi({ m, compacto }: { m: Metrica; compacto?: boolean }) {
  const [aberto, setAberto] = useState(false);
  const v = variacao(m.variacao);
  const indisponivel = m.valor === null;

  return (
    <div className={`card kpi ${indisponivel ? "indisponivel" : ""}`}>
      <div className="topo-kpi">
        <span className="nome">{m.nome}</span>
        {m.status !== "cinza" && <Pill status={m.status} texto={m.status} />}
        <button
          className="ajuda"
          aria-label={`Como ${m.nome} é calculado`}
          onMouseEnter={() => setAberto(true)}
          onMouseLeave={() => setAberto(false)}
          onFocus={() => setAberto(true)}
          onBlur={() => setAberto(false)}
          onClick={() => setAberto((a) => !a)}
        >
          ?
        </button>
      </div>

      <div className="valor">{indisponivel ? "—" : fmt(m.valor, m.unidade, compacto)}</div>

      <div className="linha">
        {m.variacao !== null && (
          <span className="var" style={{ color: corVariacao(v.sinal, m.doc.sentido) }}>
            {v.texto}
          </span>
        )}
        {m.meta !== null && <span className="meta-txt">meta {fmt(m.meta, m.unidade, true)}</span>}
        {m.detalhe && <span className="det">{m.detalhe}</span>}
      </div>

      {/* Dado insuficiente é dito, não estimado. */}
      {m.indisponivel_por && <div className="nota warn">{m.indisponivel_por}</div>}

      {m.tendencia.length > 1 && <Sparkline serie={m.tendencia} />}

      {aberto && (
        <div className="tooltip" role="tooltip">
          <dl>
            <dt>Finalidade</dt>
            <dd>{m.doc.finalidade}</dd>
            <dt>Fórmula</dt>
            <dd className="form">{m.doc.formula}</dd>
            <dt>Fonte</dt>
            <dd className="form">{m.doc.fonte}</dd>
            <dt>Interpretação</dt>
            <dd>{m.doc.interpretacao}</dd>
            {m.doc.dono && (
              <>
                <dt>Dono</dt>
                <dd>{m.doc.dono}</dd>
              </>
            )}
            {m.doc.armadilha && (
              <>
                <dt>Armadilha</dt>
                <dd>{m.doc.armadilha}</dd>
              </>
            )}
          </dl>
        </div>
      )}
    </div>
  );
}

/* ------------------------------------------------------------- medidor
   Realizado × ritmo esperado × meta, em uma barra. É o "onde deveríamos
   estar hoje" que o percentual de meta não responde. */
export function Medidor({ r }: { r: Ritmo }) {
  if (!r.meta) return <div className="nota">Sem meta definida para o período — status não avaliável.</div>;
  const p = Math.min(1, r.realizado / r.meta);
  const esperado = Math.min(1, (r.meta_esperada_hoje ?? 0) / r.meta);
  const cor = r.status === "verde" ? "var(--ok)" : r.status === "amarelo" ? "var(--warn)" : "var(--risk)";
  return (
    <div className="medidor">
      <div className="trilho">
        <div className="preenche" style={{ width: `${p * 100}%`, background: cor }} />
        <div className="marca" style={{ left: `${esperado * 100}%` }} title="ritmo esperado hoje" />
      </div>
      <div className="legenda">
        <span>{dinheiro(r.realizado, true)} realizado</span>
        <span>
          esperado hoje {dinheiro(r.meta_esperada_hoje, true)} · meta {dinheiro(r.meta, true)}
        </span>
      </div>
    </div>
  );
}

/* -------------------------------------------------------------- alerta */
export function CardAlerta({ a }: { a: Alerta }) {
  return (
    <article className={`alerta ${a.severidade}`}>
      <header>
        <Pill
          status={a.severidade === "alta" ? "vermelho" : a.severidade === "media" ? "amarelo" : "verde"}
          texto={a.severidade === "oportunidade" ? "oportunidade" : `severidade ${a.severidade}`}
        />
        <span className="regra">
          {a.regra} · {a.camada}
        </span>
        <h4>{a.titulo}</h4>
      </header>
      <div className="corpo">
        <div className="campo">
          <span className="k">O que houve</span>
          <span className="v">{a.o_que_houve}</span>
        </div>
        <div className="campo">
          <span className="k">Por que importa</span>
          <span className="v">{a.por_que_importa}</span>
        </div>
        <div className="campo">
          <span className="k">Quanto custa</span>
          <span className="v custo">{dinheiro(a.quanto_custa)}</span>
        </div>
        <div className="campo">
          <span className="k">O que fazer</span>
          <span className="v">{a.o_que_fazer}</span>
        </div>
        <div className="campo">
          <span className="k">Quem</span>
          <span className="v">
            {a.quem} · prazo sugerido: {a.prazo_dias} dias
          </span>
        </div>
      </div>
      <div className="rodape">
        {/* Insight que não leva a lugar nenhum é decoração. */}
        <a href={`#${a.destino}`}>Abrir a tela que prova este alerta →</a>
        <span className="spread" style={{ flex: 1 }} />
        <span className="pill cinza">confiança {pct(a.confianca, 0)}</span>
      </div>
    </article>
  );
}

/* ---------------------------------------------------------------- funil */
export function Funil({
  etapas,
  cor,
  destaque,
}: {
  etapas: { estagio: string; rotulo: string; volume: number; conversao_da_anterior: number | null }[];
  cor: string;
  destaque?: string;
}) {
  const max = Math.max(...etapas.map((e) => e.volume), 1);
  return (
    <div className="funil">
      {etapas.map((e) => {
        const larg = Math.max(3, (e.volume / max) * 100);
        // Barra estreita não comporta o rótulo: nesse caso o número vai para
        // FORA da barra. Truncar o texto dentro dela transformaria "49" em "4"
        // — um número errado com aparência de certo, exatamente o defeito que
        // este painel existe para evitar.
        const dentro = larg >= 14;
        return (
        <div className="linha" key={e.estagio}>
          <span className="rot">{e.rotulo}</span>
          <div className="barra-wrap">
            <div
              className="barra"
              style={{
                width: `${larg}%`,
                background: e.estagio === "S6" ? "var(--ok)" : cor,
                justifyContent: dentro ? "flex-start" : "flex-end",
              }}
            >
              {dentro && <span>{e.volume}</span>}
            </div>
            {!dentro && <span className="fora">{e.volume}</span>}
          </div>
          <span className={`conv ${destaque === e.estagio ? "pior" : ""}`}>
            {e.conversao_da_anterior !== null ? pct(e.conversao_da_anterior, 0) : "—"}
          </span>
        </div>
        );
      })}
    </div>
  );
}

/* --------------------------------------------------------------- estados */
export function Carregando({ n = 4 }: { n?: number }) {
  return (
    <div className="grade g4">
      {Array.from({ length: n }).map((_, i) => (
        <div className="skeleton" key={i} />
      ))}
    </div>
  );
}

export function Erro({ msg }: { msg: string }) {
  return (
    <div className="erro">
      Não foi possível carregar os dados. Verifique se a API está no ar em{" "}
      <strong>http://127.0.0.1:8000</strong>.<code>{msg}</code>
    </div>
  );
}

import { NavLink, Route, Routes, useSearchParams } from "react-router-dom";
import { useApi } from "./lib/api";
import Ceo from "./pages/Ceo";
import Comercial from "./pages/Comercial";
import Marketing from "./pages/Marketing";
import EmpresaPage from "./pages/Empresa";
import Insights from "./pages/Insights";
import SaudeDados from "./pages/SaudeDados";
import type { Empresa } from "./lib/types";

/**
 * Estado de filtro na URL.
 *
 * Resolve três problemas de uma vez: coerência entre telas (trocar de área
 * preserva o que se aplica), link compartilhável do problema exato, e o botão
 * voltar do navegador funcionando como qualquer pessoa espera.
 */
export function useFiltros() {
  const [params, setParams] = useSearchParams();
  return {
    periodo: params.get("periodo") ?? "2026-08",
    empresa: params.get("empresa") ?? "",
    set(chave: string, valor: string) {
      const p = new URLSearchParams(params);
      if (valor) p.set(chave, valor);
      else p.delete(chave);
      setParams(p, { replace: false });
    },
    query(extra?: Record<string, string>) {
      const p = new URLSearchParams();
      p.set("periodo", params.get("periodo") ?? "2026-08");
      const e = params.get("empresa");
      if (e) p.set("empresa", e);
      Object.entries(extra ?? {}).forEach(([k, v]) => v && p.set(k, v));
      return p.toString();
    },
  };
}

export function Cabecalho({
  titulo,
  pergunta,
  comEmpresa = true,
}: {
  titulo: string;
  pergunta: string;
  comEmpresa?: boolean;
}) {
  const f = useFiltros();
  const periodos = useApi<string[]>("/api/periodos");
  const empresas = useApi<Empresa[]>("/api/empresas");

  return (
    <div className="topo">
      <div>
        <h2>{titulo}</h2>
        <div className="sub">{pergunta}</div>
      </div>
      <span className="spread" />
      <div className="filtros">
        <label htmlFor="f-periodo">Período</label>
        <select id="f-periodo" value={f.periodo} onChange={(e) => f.set("periodo", e.target.value)}>
          {(periodos.dados ?? [f.periodo]).map((p) => (
            <option key={p} value={p}>
              {p}
            </option>
          ))}
        </select>
        {comEmpresa && (
          <>
            <label htmlFor="f-empresa">Empresa</label>
            <select id="f-empresa" value={f.empresa} onChange={(e) => f.set("empresa", e.target.value)}>
              <option value="">Todas</option>
              {(empresas.dados ?? []).map((e) => (
                <option key={e.slug} value={e.slug}>
                  {e.nome}
                </option>
              ))}
            </select>
          </>
        )}
      </div>
    </div>
  );
}

export function AvisoDemo({ ativo }: { ativo: boolean }) {
  if (!ativo) return null;
  return (
    <div className="demo-banner">
      <span className="dot vermelho" />
      DADOS DE DEMONSTRAÇÃO
      <span className="txt">
        A base oficial não foi disponibilizada. Todos os números desta tela vêm de uma carga
        sintética determinística — não representam a operação real do Grupo Mont.
      </span>
    </div>
  );
}

export default function App() {
  const empresas = useApi<Empresa[]>("/api/empresas");

  return (
    <div className="app">
      <nav className="rail">
        <div className="brand">
          <div className="mk">Painel Executivo</div>
          <h1>Grupo Mont</h1>
          <p>Montseguro · Prop5 · TechBrabo</p>
        </div>
        <div className="nav">
          <NavLink to="/" end className={({ isActive }) => (isActive ? "on" : "")}>
            <span className="n">1</span> CEO Overview
          </NavLink>
          <NavLink to="/comercial" className={({ isActive }) => (isActive ? "on" : "")}>
            <span className="n">2</span> Comercial
          </NavLink>
          <NavLink to="/marketing" className={({ isActive }) => (isActive ? "on" : "")}>
            <span className="n">3</span> Marketing
          </NavLink>
          <div className="sep">4 · Empresas</div>
          {(empresas.dados ?? []).map((e) => (
            <NavLink
              key={e.slug}
              to={`/empresas/${e.slug}`}
              className={({ isActive }) => (isActive ? "on" : "")}
            >
              <span className="n" style={{ color: e.cor }}>
                ●
              </span>{" "}
              {e.nome}
            </NavLink>
          ))}
          <div className="sep">5 · Insights</div>
          <NavLink to="/insights" className={({ isActive }) => (isActive ? "on" : "")}>
            <span className="n">!</span> Alertas e riscos
          </NavLink>
          {/* Fora do menu executivo de propósito: esta tela é de GESTÃO. O CEO
              não precisa dela; quem cuida da operação, sim. */}
          <div className="sep">Gestão</div>
          <NavLink to="/saude-dados" className={({ isActive }) => (isActive ? "on" : "")}>
            <span className="n">◈</span> Saúde dos Dados
          </NavLink>
        </div>
      </nav>

      <main className="main">
        <Routes>
          <Route path="/" element={<Ceo />} />
          <Route path="/comercial" element={<Comercial />} />
          <Route path="/marketing" element={<Marketing />} />
          <Route path="/empresas/:slug" element={<EmpresaPage />} />
          <Route path="/insights" element={<Insights />} />
          <Route path="/saude-dados" element={<SaudeDados />} />
        </Routes>
      </main>
    </div>
  );
}

import { Navigate, NavLink, Outlet, Link, useLocation } from "react-router";
import { useSession } from "../session.tsx";
import { Brand, Loading } from "./ui.tsx";
import { PLANS } from "../../shared/plans.ts";

export function PublicLayout() {
  const { me } = useSession();
  return (
    <>
      <header className="topbar">
        <div className="container">
          <Brand />
          <nav className="nav-links">
            <a href="/#como-funciona">Como funciona</a>
            <a href="/#multiplicador">Multiplicador</a>
            <a href="/#produtos">Produtos</a>
            <Link to="/planos">Planos</Link>
            <a href="/#faq">Dúvidas</a>
          </nav>
          <div className="spacer" />
          {me ? (
            <Link className="btn primary sm" to="/app">
              Abrir painel
            </Link>
          ) : (
            <div className="row">
              <Link className="btn ghost sm" to="/entrar">
                Entrar
              </Link>
              <Link className="btn primary sm" to="/criar-conta">
                Testar grátis
              </Link>
            </div>
          )}
        </div>
      </header>
      <Outlet />
      <footer className="site">
        <div className="container row between">
          <span>© {new Date().getFullYear()} Facilitador TikTok Shop</span>
          <span>Ferramenta independente, sem vínculo com o TikTok ou a ByteDance.</span>
        </div>
      </footer>
    </>
  );
}

const LINKS = [
  { to: "/app", label: "Painel", ico: "◧", end: true },
  { to: "/app/multiplicador", label: "Multiplicador", ico: "✦" },
  { to: "/app/produtos", label: "Produtos em alta", ico: "↗" },
  { to: "/app/roteiros", label: "Roteiros com IA", ico: "✎" },
  { to: "/app/conta", label: "Minha conta", ico: "◉" },
];

export function AppLayout() {
  const { me, loading } = useSession();
  const location = useLocation();
  if (loading) return <Loading />;
  if (!me) return <Navigate to={`/entrar?voltar=${encodeURIComponent(location.pathname)}`} replace />;
  const links = me.user.isAdmin ? [...LINKS, { to: "/app/admin", label: "Admin", ico: "⚙" }] : LINKS;
  const nav = links.map((l) => (
    <NavLink key={l.to} to={l.to} end={l.end} className={({ isActive }) => `side-link ${isActive ? "active" : ""}`}>
      <span className="ico">{l.ico}</span>
      {l.label}
    </NavLink>
  ));
  return (
    <div className="app">
      <aside className="sidebar">
        <Brand />
        {nav}
        <div className="spacer" />
        <div className="card" style={{ padding: 14 }}>
          <div className="small muted">Plano</div>
          <strong>{PLANS[me.user.plan].name}</strong>
          {me.user.plan !== "pro" && (
            <Link to="/planos" className="btn primary sm" style={{ marginTop: 10, width: "100%" }}>
              Fazer upgrade
            </Link>
          )}
        </div>
      </aside>
      <nav className="mobile-bar">{nav}</nav>
      <main className="main">
        <Outlet />
      </main>
    </div>
  );
}

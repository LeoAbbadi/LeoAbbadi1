import { useState } from "react";
import { Link, Navigate, NavLink, useLocation, useOutlet } from "react-router";
import { AnimatePresence, motion } from "motion/react";
import { useSession } from "../session.tsx";
import { Brand, Loading } from "./ui.tsx";
import { Aurora, EASE } from "./fx.tsx";
import { Icon } from "./Icons.tsx";
import { PLANS } from "../../shared/plans.ts";

const PUBLIC_LINKS = [
  { href: "/#como-funciona", label: "Como funciona" },
  { href: "/#multiplicador", label: "Multiplicador" },
  { href: "/#produtos", label: "Produtos" },
  { href: "/planos", label: "Planos" },
  { href: "/#faq", label: "Dúvidas" },
];

function TopBar() {
  const { me } = useSession();
  const [hover, setHover] = useState<number | null>(null);
  return (
    <motion.header
      className="topbar"
      initial={{ y: -40, opacity: 0 }}
      animate={{ y: 0, opacity: 1 }}
      transition={{ duration: 0.9, ease: EASE, delay: 0.1 }}
    >
      <div className="container">
        <div className="bar glass">
          <Brand />
          <nav className="nav-links" onPointerLeave={() => setHover(null)}>
            {PUBLIC_LINKS.map((l, i) => (
              <a key={l.href} href={l.href} onPointerEnter={() => setHover(i)}>
                {hover === i && (
                  <motion.span layoutId="nav-hover" className="nav-hover" transition={{ type: "spring", stiffness: 380, damping: 32 }} />
                )}
                {l.label}
              </a>
            ))}
          </nav>
          <div className="spacer" />
          {me ? (
            <Link className="btn primary" to="/app">
              Abrir painel <Icon.Arrow />
            </Link>
          ) : (
            <div className="row" style={{ gap: 8 }}>
              <Link className="btn ghost" to="/entrar">
                Entrar
              </Link>
              <Link className="btn primary" to="/criar-conta">
                Testar grátis <Icon.Arrow />
              </Link>
            </div>
          )}
        </div>
      </div>
    </motion.header>
  );
}

export function PublicLayout() {
  const outlet = useOutlet();
  return (
    <>
      <Aurora />
      <TopBar />
      {outlet}
      <footer className="site">
        <div className="container row between">
          <span>© {new Date().getFullYear()} Facilitador TikTok Shop</span>
          <span>Ferramenta independente, sem vínculo com o TikTok ou a ByteDance.</span>
        </div>
      </footer>
    </>
  );
}

const APP_LINKS = [
  { to: "/app", label: "Painel", icon: <Icon.Grid />, end: true },
  { to: "/app/multiplicador", label: "Multiplicador", icon: <Icon.Layers /> },
  { to: "/app/produtos", label: "Produtos em alta", icon: <Icon.Trend /> },
  { to: "/app/roteiros", label: "Roteiros com IA", icon: <Icon.Pen /> },
  { to: "/app/conta", label: "Minha conta", icon: <Icon.User /> },
];

function SideNav({ links, id }: { links: typeof APP_LINKS; id: string }) {
  const { pathname } = useLocation();
  const isActive = (to: string, end?: boolean) => (end ? pathname === to : pathname === to || pathname.startsWith(`${to}/`));
  return (
    <>
      {links.map((l) => {
        const active = isActive(l.to, l.end) || (l.to === "/app/multiplicador" && pathname.startsWith("/app/lotes"));
        return (
          <NavLink key={l.to} to={l.to} end={l.end} className={`side-link ${active ? "active" : ""}`}>
            {active && <motion.span layoutId={id} className="side-active" transition={{ type: "spring", stiffness: 420, damping: 34 }} />}
            <span className="ico">{l.icon}</span>
            {l.label}
          </NavLink>
        );
      })}
    </>
  );
}

export function AppLayout() {
  const { me, loading } = useSession();
  const location = useLocation();
  const outlet = useOutlet();
  if (loading) return <Loading />;
  if (!me) return <Navigate to={`/entrar?voltar=${encodeURIComponent(location.pathname)}`} replace />;
  const links = me.user.isAdmin ? [...APP_LINKS, { to: "/app/admin", label: "Admin", icon: <Icon.Gear />, end: false }] : APP_LINKS;
  return (
    <div className="app">
      <Aurora />
      <motion.aside
        className="sidebar glass"
        initial={{ x: -30, opacity: 0 }}
        animate={{ x: 0, opacity: 1 }}
        transition={{ duration: 0.8, ease: EASE }}
      >
        <Brand />
        <SideNav links={links} id="side-active" />
        <div className="spacer" />
        <div className="glass dark" style={{ padding: 16, borderRadius: 18 }}>
          <div className="small muted">Seu plano</div>
          <div className="serif" style={{ fontSize: "1.7rem", lineHeight: 1.1 }}>
            {PLANS[me.user.plan].name}
          </div>
          {me.user.plan !== "pro" && (
            <Link to="/planos" className="btn primary sm" style={{ marginTop: 12, width: "100%" }}>
              Fazer upgrade
            </Link>
          )}
        </div>
      </motion.aside>
      <nav className="mobile-bar glass">
        <SideNav links={links} id="mobile-active" />
      </nav>
      <main className="main">
        <AnimatePresence mode="wait">
          <motion.div
            key={location.pathname}
            initial={{ opacity: 0, y: 18, filter: "blur(8px)" }}
            animate={{ opacity: 1, y: 0, filter: "blur(0px)" }}
            exit={{ opacity: 0, y: -10, filter: "blur(6px)" }}
            transition={{ duration: 0.45, ease: EASE }}
          >
            {outlet}
          </motion.div>
        </AnimatePresence>
      </main>
    </div>
  );
}

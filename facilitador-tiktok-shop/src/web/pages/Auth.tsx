import { useState, type FormEvent } from "react";
import { Link, Navigate, useNavigate, useSearchParams } from "react-router";
import { api } from "../api.ts";
import { Brand, ErrorBox } from "../components/ui.tsx";
import { useSession } from "../session.tsx";
import { motion } from "motion/react";
import { Aurora, EASE } from "../components/fx.tsx";
import { HeroScene } from "../components/Scene.tsx";

export function AuthPage({ mode }: { mode: "login" | "signup" }) {
  const { me, refresh } = useSession();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);

  const plan = params.get("plano");
  const back = params.get("voltar") ?? (plan && plan !== "free" ? "/planos" : "/app");
  if (me) return <Navigate to={back} replace />;

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api(mode === "login" ? "/api/auth/login" : "/api/auth/signup", {
        body: mode === "login" ? { email, password } : { name, email, password },
      });
      await refresh();
      navigate(back, { replace: true });
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="auth-wrap">
      <Aurora />
      <div className="hero-scene" style={{ position: "fixed", inset: 0, zIndex: -1, opacity: 0.55 }}>
        <HeroScene />
      </div>
      <motion.div
        className="auth-card stack"
        style={{ gap: 20 }}
        initial={{ opacity: 0, y: 30, scale: 0.97, filter: "blur(12px)" }}
        animate={{ opacity: 1, y: 0, scale: 1, filter: "blur(0px)" }}
        transition={{ duration: 0.9, ease: EASE }}
      >
        <div className="center row" style={{ justifyContent: "center" }}>
          <Brand />
        </div>
        <form className="glass strong stack" style={{ padding: 30, borderRadius: 28 }} onSubmit={submit}>
          <h2 style={{ fontSize: "2.4rem", marginBottom: 4 }}>{mode === "login" ? "Entrar" : "Criar conta grátis"}</h2>
          {mode === "signup" && (
            <label className="field">
              Seu nome
              <input value={name} onChange={(e) => setName(e.target.value)} required autoComplete="name" />
            </label>
          )}
          <label className="field">
            E-mail
            <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required autoComplete="email" />
          </label>
          <label className="field">
            Senha
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              minLength={mode === "signup" ? 8 : undefined}
              autoComplete={mode === "login" ? "current-password" : "new-password"}
            />
            {mode === "signup" && <span className="hint">Pelo menos 8 caracteres.</span>}
          </label>
          <ErrorBox error={error} />
          <button className="btn primary" disabled={busy}>
            {busy ? "Aguarde..." : mode === "login" ? "Entrar" : "Criar conta"}
          </button>
          <p className="small muted center" style={{ margin: 0 }}>
            {mode === "login" ? (
              <>
                Ainda não tem conta? <Link to={`/criar-conta${params.size ? `?${params}` : ""}`}>Criar conta grátis</Link>
              </>
            ) : (
              <>
                Já tem conta? <Link to={`/entrar${params.size ? `?${params}` : ""}`}>Entrar</Link>
              </>
            )}
          </p>
        </form>
      </motion.div>
    </div>
  );
}

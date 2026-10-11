import { useCallback, useEffect, useState, type ReactNode } from "react";
import { Link } from "react-router";

export function Brand() {
  return (
    <Link to="/" className="brand">
      <span className="brand-mark" aria-hidden>
        <svg width="18" height="18" viewBox="0 0 64 64">
          <path d="M8 18h18v28H8zM32 8h22v18H32zM32 32h22v24H32z" fill="#1a0a04" />
        </svg>
      </span>
      <span>
        Facilitador
        <small>TikTok Shop</small>
      </span>
    </Link>
  );
}

export function Spinner() {
  return <div className="spinner" role="status" aria-label="Carregando" />;
}

export function Loading() {
  return (
    <div className="empty">
      <div className="row" style={{ justifyContent: "center" }}>
        <Spinner />
      </div>
    </div>
  );
}

export function ErrorBox({ error }: { error: unknown }) {
  if (!error) return null;
  return <div className="alert error">{error instanceof Error ? error.message : String(error)}</div>;
}

export function Meter({ label, used, limit }: { label: string; used: number; limit: number }) {
  const pct = Math.min(100, Math.round((used / Math.max(1, limit)) * 100));
  return (
    <div className="meter">
      <div className="row between small">
        <span className="muted">{label}</span>
        <strong>
          {used.toLocaleString("pt-BR")} / {limit.toLocaleString("pt-BR")}
        </strong>
      </div>
      <div className="progress">
        <div style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

export function PageHead({ title, sub, actions }: { title: string; sub?: ReactNode; actions?: ReactNode }) {
  return (
    <div className="page-head">
      <div>
        <h1>{title}</h1>
        {sub && <p className="muted" style={{ margin: "6px 0 0" }}>{sub}</p>}
      </div>
      {actions && <div className="row">{actions}</div>}
    </div>
  );
}

/** Carrega dados de uma função assíncrona e permite recarregar. */
export function useLoad<T>(fn: () => Promise<T>, deps: unknown[]) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [loading, setLoading] = useState(true);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const load = useCallback(fn, deps);
  const reload = useCallback(async () => {
    try {
      setData(await load());
      setError(null);
    } catch (err) {
      setError(err);
    } finally {
      setLoading(false);
    }
  }, [load]);
  useEffect(() => {
    setLoading(true);
    void reload();
  }, [reload]);
  return { data, error, loading, reload, setData };
}

export function CopyButton({ text, label = "Copiar" }: { text: string; label?: string }) {
  const [done, setDone] = useState(false);
  return (
    <button
      className="btn sm"
      type="button"
      onClick={async () => {
        await navigator.clipboard.writeText(text);
        setDone(true);
        setTimeout(() => setDone(false), 1500);
      }}
    >
      {done ? "Copiado!" : label}
    </button>
  );
}

import { useState } from "react";
import { useNavigate } from "react-router";
import { motion } from "motion/react";
import { api } from "../api.ts";
import { useOpenLink } from "./ui.tsx";
import { useSession } from "../session.tsx";
import { PLANS, formatBRL, type BillingPeriod, type PlanId } from "../../shared/plans.ts";

export function Pricing() {
  const [period, setPeriod] = useState<BillingPeriod>("monthly");
  const { me, refresh } = useSession();
  const navigate = useNavigate();
  const openLink = useOpenLink();
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function choose(plan: PlanId) {
    if (!me) return navigate(`/criar-conta?plano=${plan}&periodo=${period}`);
    if (plan === "free") return navigate("/app");
    setBusy(plan);
    setError(null);
    try {
      const { url } = await api<{ url: string }>("/api/billing/checkout", { body: { plan, period } });
      if (url.startsWith("app:")) await refresh();
      openLink(url);
    } catch (err) {
      setError((err as Error).message);
      setBusy(null);
    }
  }

  const pro = PLANS.pro;
  const annualSaving = pro.monthlyCents! * 12 - pro.annualCents!;
  const plans = [PLANS.free, PLANS.starter, PLANS.pro];

  return (
    <div className="stack" style={{ gap: 28 }}>
      <div className="row" style={{ justifyContent: "center" }}>
        <div className="toggle" role="tablist">
          {(["monthly", "annual"] as const).map((p) => (
            <button key={p} className={period === p ? "on" : ""} onClick={() => setPeriod(p)}>
              {period === p && <motion.span layoutId="price-toggle" className="toggle-bg" transition={{ type: "spring", stiffness: 420, damping: 34 }} />}
              {p === "monthly" ? "Mensal" : <>Anual <span className="mint small">economize {formatBRL(annualSaving)}</span></>}
            </button>
          ))}
        </div>
      </div>
      {error && <div className="alert error">{error}</div>}
      <div className="grid cols-3">
        {plans.map((plan) => {
          const annual = period === "annual" && plan.annualCents;
          const unavailable = period === "annual" && plan.id === "starter";
          const current = me?.user.plan === plan.id;
          return (
            <motion.div key={plan.id} className={`card pad-lg price-card ${plan.id === "pro" ? "featured" : ""}`} whileHover={{ y: -8 }} transition={{ type: "spring", stiffness: 300, damping: 24 }}>
              {plan.id === "pro" && <span className="ribbon">Mais completo</span>}
              <div>
                <h3 style={{ marginBottom: 4 }}>{plan.name}</h3>
                <div className="muted small">{plan.tagline}</div>
              </div>
              <div>
                {plan.id === "free" ? (
                  <div className="price">R$ 0</div>
                ) : annual ? (
                  <>
                    <div className="price">
                      {formatBRL(Math.round(plan.annualCents! / 12))}
                      <span className="muted small" style={{ fontWeight: 500 }}>/mês</span>
                    </div>
                    <div className="muted small">{formatBRL(plan.annualCents!)} por ano, à vista ou parcelado</div>
                  </>
                ) : (
                  <>
                    <div className="price">
                      {formatBRL(plan.monthlyCents!)}
                      <span className="muted small" style={{ fontWeight: 500 }}>/mês</span>
                    </div>
                    <div className="muted small">Cancele quando quiser</div>
                  </>
                )}
              </div>
              <ul>
                {plan.features.map((f) => (
                  <li key={f}>{f}</li>
                ))}
              </ul>
              <div className="spacer" />
              <button
                className={`btn ${plan.id === "pro" ? "primary" : ""}`}
                disabled={busy !== null || unavailable || current}
                onClick={() => choose(plan.id)}
              >
                {current
                  ? "Seu plano atual"
                  : unavailable
                    ? "Só no mensal"
                    : busy === plan.id
                      ? "Abrindo pagamento..."
                      : plan.id === "free"
                        ? "Começar grátis"
                        : `Assinar ${plan.name}`}
              </button>
            </motion.div>
          );
        })}
      </div>
      <p className="center faint small">7 dias de garantia: não gostou, devolvemos 100% do valor. Pagamento seguro por cartão ou Pix.</p>
    </div>
  );
}

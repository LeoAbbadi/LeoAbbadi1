// Cota mensal de vídeos e roteiros. A reserva é atômica: dois pedidos ao mesmo
// tempo não conseguem passar do limite do plano.
import { currentPeriod, one, query } from "./db.ts";
import { PLANS, type PlanId } from "../shared/plans.ts";

export type UsageKind = "videos" | "scripts";

export async function getUsage(userId: string): Promise<{ videos: number; scripts: number }> {
  const row = await one<{ videos: number; scripts: number }>(
    "SELECT videos, scripts FROM usage WHERE user_id = $1 AND period = $2",
    [userId, currentPeriod()],
  );
  return row ?? { videos: 0, scripts: 0 };
}

export function limitFor(plan: PlanId, kind: UsageKind): number {
  return kind === "videos" ? PLANS[plan].videosPerMonth : PLANS[plan].scriptsPerMonth;
}

/** Reserva `amount` unidades. Devolve false se passaria do limite. */
export async function reserve(userId: string, plan: PlanId, kind: UsageKind, amount: number): Promise<boolean> {
  const limit = limitFor(plan, kind);
  if (amount > limit) return false;
  // kind vem de um tipo fechado, então é seguro interpolar o nome da coluna
  const rows = await query(
    `INSERT INTO usage(user_id, period, ${kind}) VALUES ($1, $2, $3)
     ON CONFLICT (user_id, period) DO UPDATE SET ${kind} = usage.${kind} + EXCLUDED.${kind}
       WHERE usage.${kind} + EXCLUDED.${kind} <= $4
     RETURNING ${kind}`,
    [userId, currentPeriod(), amount, limit],
  );
  return rows.length > 0;
}

export async function refund(userId: string, kind: UsageKind, amount: number, period = currentPeriod()): Promise<void> {
  if (amount <= 0) return;
  await query(`UPDATE usage SET ${kind} = GREATEST(0, ${kind} - $3) WHERE user_id = $1 AND period = $2`, [
    userId,
    period,
    amount,
  ]);
}

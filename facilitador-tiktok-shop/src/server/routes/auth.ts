import type { FastifyInstance } from "fastify";
import { z } from "zod";
import {
  HttpError,
  currentUser,
  effectivePlan,
  endSession,
  hashPassword,
  isAdmin,
  startSession,
  verifyPassword,
  type User,
} from "../auth.ts";
import { one } from "../db.ts";
import { getUsage } from "../usage.ts";
import { PLANS } from "../../shared/plans.ts";

const signupBody = z.object({
  name: z.string().trim().min(2, "Digite seu nome.").max(80),
  email: z.string().trim().toLowerCase().email("E-mail inválido."),
  password: z.string().min(8, "A senha precisa de pelo menos 8 caracteres.").max(200),
});
const loginBody = z.object({ email: z.string().trim().toLowerCase(), password: z.string() });

export async function authRoutes(app: FastifyInstance) {
  app.post("/api/auth/signup", async (request, reply) => {
    const body = signupBody.parse(request.body);
    const exists = await one("SELECT 1 FROM users WHERE email = $1", [body.email]);
    if (exists) throw new HttpError(409, "Já existe uma conta com esse e-mail.");
    const user = await one<{ id: string }>(
      "INSERT INTO users(email, name, password_hash) VALUES ($1, $2, $3) RETURNING id",
      [body.email, body.name, await hashPassword(body.password)],
    );
    await startSession(reply, user!.id);
    return { ok: true };
  });

  app.post("/api/auth/login", async (request, reply) => {
    const body = loginBody.parse(request.body);
    const row = await one<{ id: string; password_hash: string }>(
      "SELECT id, password_hash FROM users WHERE email = $1",
      [body.email],
    );
    if (!row || !(await verifyPassword(body.password, row.password_hash))) {
      throw new HttpError(401, "E-mail ou senha incorretos.");
    }
    await startSession(reply, row.id);
    return { ok: true };
  });

  app.post("/api/auth/logout", async (request, reply) => {
    await endSession(request, reply);
    return { ok: true };
  });

  app.get("/api/me", async (request) => {
    const user = await currentUser(request);
    if (!user) return { user: null };
    return mePayload(user);
  });
}

export async function mePayload(user: User) {
  const plan = PLANS[effectivePlan(user)];
  const usage = await getUsage(user.id);
  return {
    user: {
      id: user.id,
      email: user.email,
      name: user.name,
      isAdmin: isAdmin(user),
      plan: plan.id,
      planPeriod: user.plan_period,
      planStatus: user.plan_status,
      planRenewsAt: user.plan_renews_at,
      hasBilling: Boolean(user.stripe_customer_id),
    },
    limits: {
      videosPerMonth: plan.videosPerMonth,
      maxVideosPerBatch: plan.maxVideosPerBatch,
      scriptsPerMonth: plan.scriptsPerMonth,
      countries: plan.countries,
    },
    usage,
  };
}

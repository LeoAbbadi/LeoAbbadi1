import crypto from "node:crypto";
import { promisify } from "node:util";
import type { FastifyReply, FastifyRequest } from "fastify";
import { config } from "./config.ts";
import { one, query } from "./db.ts";
import type { PlanId } from "../shared/plans.ts";

const scrypt = promisify(crypto.scrypt) as (pw: string, salt: Buffer, len: number) => Promise<Buffer>;
const SESSION_DAYS = 30;
export const SESSION_COOKIE = "fts_session";

export interface User {
  id: string;
  email: string;
  name: string;
  plan: PlanId;
  plan_period: "monthly" | "annual" | null;
  plan_status: string;
  plan_renews_at: string | null;
  stripe_customer_id: string | null;
  stripe_subscription_id: string | null;
}

export const USER_COLUMNS =
  "id, email, name, plan, plan_period, plan_status, plan_renews_at, stripe_customer_id, stripe_subscription_id";

export async function hashPassword(password: string): Promise<string> {
  const salt = crypto.randomBytes(16);
  const hash = await scrypt(password, salt, 64);
  return `scrypt$${salt.toString("hex")}$${hash.toString("hex")}`;
}

export async function verifyPassword(password: string, stored: string): Promise<boolean> {
  const [, saltHex, hashHex] = stored.split("$");
  if (!saltHex || !hashHex) return false;
  const hash = await scrypt(password, Buffer.from(saltHex, "hex"), 64);
  const expected = Buffer.from(hashHex, "hex");
  return expected.length === hash.length && crypto.timingSafeEqual(expected, hash);
}

const tokenHash = (token: string) => crypto.createHash("sha256").update(token).digest("hex");

export async function startSession(reply: FastifyReply, userId: string): Promise<void> {
  const token = crypto.randomBytes(32).toString("base64url");
  const expires = new Date(Date.now() + SESSION_DAYS * 86400_000);
  await query("INSERT INTO sessions(token_hash, user_id, expires_at) VALUES ($1, $2, $3)", [
    tokenHash(token),
    userId,
    expires,
  ]);
  reply.setCookie(SESSION_COOKIE, token, {
    path: "/",
    httpOnly: true,
    sameSite: "lax",
    secure: config.isProduction,
    expires,
  });
}

export async function endSession(request: FastifyRequest, reply: FastifyReply): Promise<void> {
  const token = request.cookies[SESSION_COOKIE];
  if (token) await query("DELETE FROM sessions WHERE token_hash = $1", [tokenHash(token)]);
  reply.clearCookie(SESSION_COOKIE, { path: "/" });
}

export async function currentUser(request: FastifyRequest): Promise<User | null> {
  const token = request.cookies[SESSION_COOKIE];
  if (!token) return null;
  const user = await one<User>(
    `SELECT ${USER_COLUMNS.split(", ").map((c) => `u.${c}`).join(", ")}
       FROM sessions s JOIN users u ON u.id = s.user_id
      WHERE s.token_hash = $1 AND s.expires_at > now()`,
    [tokenHash(token)],
  );
  return user ?? null;
}

export class HttpError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

export async function requireUser(request: FastifyRequest): Promise<User> {
  const user = await currentUser(request);
  if (!user) throw new HttpError(401, "Faça login para continuar.");
  return user;
}

export function isAdmin(user: User): boolean {
  return config.adminEmails.includes(user.email.toLowerCase());
}

/** Plano que vale agora: assinatura cancelada ou com pagamento atrasado volta para o grátis. */
export function effectivePlan(user: User): PlanId {
  if (user.plan === "free") return "free";
  if (user.plan_status === "active") return user.plan;
  if (user.plan_renews_at && new Date(user.plan_renews_at) > new Date()) return user.plan;
  return "free";
}

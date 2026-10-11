// Assinaturas com Stripe (cartão; Pix no plano anual se ativado no painel da Stripe).
// Sem STRIPE_SECRET_KEY o checkout ativa o plano na hora: modo demonstração para desenvolvimento.
import type { FastifyInstance } from "fastify";
import Stripe from "stripe";
import { z } from "zod";
import { HttpError, requireUser } from "../auth.ts";
import { config } from "../config.ts";
import { one, query } from "../db.ts";

const stripe = config.stripe.secretKey ? new Stripe(config.stripe.secretKey) : null;

const checkoutBody = z.object({
  plan: z.enum(["starter", "pro"]),
  period: z.enum(["monthly", "annual"]),
});

export async function billingRoutes(app: FastifyInstance) {
  app.post("/api/billing/checkout", async (request) => {
    const user = await requireUser(request);
    const { plan, period } = checkoutBody.parse(request.body);
    const priceKey = `${plan}_${period}`;

    if (!stripe) {
      if (config.isProduction) throw new HttpError(503, "Pagamentos ainda não configurados.");
      const renews = new Date();
      renews.setMonth(renews.getMonth() + (period === "annual" ? 12 : 1));
      await query("UPDATE users SET plan = $2, plan_period = $3, plan_status = 'active', plan_renews_at = $4 WHERE id = $1", [
        user.id,
        plan,
        period,
        renews,
      ]);
      return { url: `${config.appUrl}/app/conta?assinatura=ok` };
    }

    const price = config.stripe.prices[priceKey];
    if (!price) throw new HttpError(400, "Esse plano não está disponível nesse período.");
    let customer = user.stripe_customer_id;
    if (!customer) {
      customer = (await stripe.customers.create({ email: user.email, name: user.name, metadata: { userId: user.id } })).id;
      await query("UPDATE users SET stripe_customer_id = $2 WHERE id = $1", [user.id, customer]);
    }
    const session = await stripe.checkout.sessions.create({
      mode: "subscription",
      customer,
      line_items: [{ price, quantity: 1 }],
      client_reference_id: user.id,
      subscription_data: { metadata: { userId: user.id, plan, period } },
      allow_promotion_codes: true,
      locale: "pt-BR",
      success_url: `${config.appUrl}/app/conta?assinatura=ok`,
      cancel_url: `${config.appUrl}/planos`,
    });
    return { url: session.url };
  });

  app.post("/api/billing/portal", async (request) => {
    const user = await requireUser(request);
    if (!stripe || !user.stripe_customer_id) throw new HttpError(400, "Nenhuma assinatura para gerenciar.");
    const portal = await stripe.billingPortal.sessions.create({
      customer: user.stripe_customer_id,
      return_url: `${config.appUrl}/app/conta`,
    });
    return { url: portal.url };
  });

  // Webhook precisa do corpo cru para validar a assinatura da Stripe
  app.register(async (scope) => {
    scope.addContentTypeParser("application/json", { parseAs: "buffer" }, (_req, body, done) => done(null, body));
    scope.post("/api/billing/webhook", async (request, reply) => {
      if (!stripe) return reply.code(404).send();
      let event: Stripe.Event;
      try {
        event = stripe.webhooks.constructEvent(
          request.body as Buffer,
          String(request.headers["stripe-signature"] ?? ""),
          config.stripe.webhookSecret,
        );
      } catch {
        return reply.code(400).send({ error: "assinatura inválida" });
      }
      if (event.type.startsWith("customer.subscription.")) {
        await syncSubscription(event.data.object as Stripe.Subscription);
      }
      return { received: true };
    });
  });
}

async function syncSubscription(sub: Stripe.Subscription) {
  const userId = sub.metadata.userId;
  const plan = sub.metadata.plan;
  const period = sub.metadata.period;
  if (!userId || !plan) return;
  const status = sub.status === "active" || sub.status === "trialing" ? "active" : sub.status === "past_due" ? "past_due" : "canceled";
  const periodEnd = sub.items.data[0]?.current_period_end;
  const user = await one("SELECT id FROM users WHERE id = $1", [userId]);
  if (!user) return;
  await query(
    `UPDATE users SET plan = $2, plan_period = $3, plan_status = $4, plan_renews_at = $5, stripe_subscription_id = $6 WHERE id = $1`,
    [userId, status === "canceled" && !periodEnd ? "free" : plan, period, status, periodEnd ? new Date(periodEnd * 1000) : null, sub.id],
  );
}

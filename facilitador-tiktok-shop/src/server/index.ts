import fs from "node:fs";
import path from "node:path";
import Fastify from "fastify";
import cookie from "@fastify/cookie";
import fastifyStatic from "@fastify/static";
import { ZodError } from "zod";
import { HttpError } from "./auth.ts";
import { config } from "./config.ts";
import { migrate } from "./migrate.ts";
import { authRoutes } from "./routes/auth.ts";
import { billingRoutes } from "./routes/billing.ts";
import { fileRoutes } from "./routes/files.ts";
import { multiplicadorRoutes } from "./routes/multiplicador.ts";
import { productRoutes } from "./routes/products.ts";
import { scriptRoutes } from "./routes/scripts.ts";

export async function buildServer() {
  const app = Fastify({ logger: { level: config.isProduction ? "info" : "warn" }, bodyLimit: 25 * 1024 * 1024 });
  await app.register(cookie);

  app.setErrorHandler((err, request, reply) => {
    if (err instanceof HttpError) return reply.code(err.status).send({ error: err.message });
    if (err instanceof ZodError) return reply.code(400).send({ error: err.issues[0]?.message ?? "Dados inválidos." });
    const status = (err as { statusCode?: number }).statusCode;
    if (status && status < 500) return reply.code(status).send({ error: (err as Error).message });
    request.log.error(err);
    return reply.code(500).send({ error: "Algo deu errado. Tente de novo." });
  });

  app.get("/api/health", async () => ({ ok: true }));
  await app.register(authRoutes);
  await app.register(multiplicadorRoutes);
  await app.register(scriptRoutes);
  await app.register(productRoutes);
  await app.register(billingRoutes);
  await app.register(fileRoutes);

  // Em produção o mesmo servidor entrega o site (pasta dist gerada pelo Vite)
  const dist = path.resolve("dist");
  if (fs.existsSync(dist)) {
    await app.register(fastifyStatic, { root: dist });
    app.setNotFoundHandler((request, reply) => {
      if (request.url.startsWith("/api/")) return reply.code(404).send({ error: "Não encontrado." });
      return reply.sendFile("index.html");
    });
  }
  return app;
}

if (import.meta.url === `file://${process.argv[1]}`) {
  await migrate();
  const app = await buildServer();
  await app.listen({ port: config.port, host: "0.0.0.0" });
  console.log(`API rodando em http://localhost:${config.port}`);
}

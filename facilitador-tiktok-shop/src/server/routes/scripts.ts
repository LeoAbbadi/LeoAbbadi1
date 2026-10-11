import type { FastifyInstance } from "fastify";
import { z } from "zod";
import Anthropic from "@anthropic-ai/sdk";
import { generateScript, scriptInput } from "../ai.ts";
import { HttpError, effectivePlan, requireUser } from "../auth.ts";
import { one, query } from "../db.ts";
import { refund, reserve } from "../usage.ts";

export async function scriptRoutes(app: FastifyInstance) {
  app.get("/api/scripts", async (request) => {
    const user = await requireUser(request);
    return query(
      "SELECT id, kind, product_name, created_at FROM scripts WHERE user_id = $1 ORDER BY created_at DESC LIMIT 100",
      [user.id],
    );
  });

  app.get("/api/scripts/:id", async (request) => {
    const user = await requireUser(request);
    const id = z.string().uuid().parse((request.params as { id: string }).id);
    const row = await one("SELECT id, kind, product_name, input, output, created_at FROM scripts WHERE id = $1 AND user_id = $2", [
      id,
      user.id,
    ]);
    if (!row) throw new HttpError(404, "Roteiro não encontrado.");
    return row;
  });

  app.post("/api/scripts", async (request) => {
    const user = await requireUser(request);
    const input = scriptInput.parse(request.body);
    const plan = effectivePlan(user);
    if (!(await reserve(user.id, plan, "scripts", 1))) {
      throw new HttpError(402, "Você usou todos os roteiros do seu plano este mês.");
    }
    try {
      const result = await generateScript(input);
      return await one(
        `INSERT INTO scripts(user_id, kind, product_name, input, output, model, input_tokens, output_tokens)
         VALUES ($1, $2, $3, $4, $5, $6, $7, $8) RETURNING id, kind, product_name, input, output, created_at`,
        [user.id, input.kind, input.productName, input, result.output, result.model, result.inputTokens, result.outputTokens],
      );
    } catch (err) {
      await refund(user.id, "scripts", 1);
      if (err instanceof Anthropic.RateLimitError) throw new HttpError(429, "Muita gente gerando agora. Tente em 1 minuto.");
      if (err instanceof Anthropic.APIError) {
        request.log.error({ err }, "erro na API da Anthropic");
        throw new HttpError(502, "A IA está indisponível agora. Tente de novo em instantes.");
      }
      throw err;
    }
  });

  app.delete("/api/scripts/:id", async (request) => {
    const user = await requireUser(request);
    const id = z.string().uuid().parse((request.params as { id: string }).id);
    await query("DELETE FROM scripts WHERE id = $1 AND user_id = $2", [id, user.id]);
    return { ok: true };
  });
}

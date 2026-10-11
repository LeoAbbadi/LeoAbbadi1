// Só usado com STORAGE_DRIVER=local: recebe e entrega os arquivos que, em produção,
// iriam direto para o R2/S3. Os links são assinados e expiram.
import fs from "node:fs";
import path from "node:path";
import type { FastifyInstance } from "fastify";
import { HttpError } from "../auth.ts";
import { localPathFor, localStorage, verifyLocalSignature } from "../storage/index.ts";
import { MAX_CLIP_BYTES } from "../../shared/plans.ts";

const MIME: Record<string, string> = { ".mp4": "video/mp4", ".mov": "video/quicktime", ".zip": "application/zip", ".webm": "video/webm" };

export async function fileRoutes(app: FastifyInstance) {
  if (!localStorage) return;
  const local = localStorage;

  app.addContentTypeParser("*", (_request, payload, done) => done(null, payload));

  function check(params: unknown, q: unknown, method: string): string {
    const key = decodeURI((params as { "*": string })["*"]);
    const { exp, sig } = q as { exp?: string; sig?: string };
    if (!sig || !verifyLocalSignature(key, method, Number(exp), sig)) throw new HttpError(403, "Link inválido ou expirado.");
    return key;
  }

  app.put("/api/files/*", async (request) => {
    const key = check(request.params, request.query, "PUT");
    await local.writeStream(key, request.body as NodeJS.ReadableStream as never, MAX_CLIP_BYTES);
    return { ok: true };
  });

  app.get("/api/files/*", async (request, reply) => {
    const key = check(request.params, request.query, "GET");
    const file = localPathFor(key);
    let stat: fs.Stats;
    try {
      stat = fs.statSync(file);
    } catch {
      throw new HttpError(404, "Arquivo não encontrado.");
    }
    const type = MIME[path.extname(file).toLowerCase()] ?? "application/octet-stream";
    const name = (request.query as { name?: string }).name;
    reply.header("Content-Type", type).header("Accept-Ranges", "bytes");
    if (name) reply.header("Content-Disposition", `attachment; filename="${name.replace(/"/g, "")}"`);

    // suporte a Range para o player de vídeo do navegador
    const range = request.headers.range?.match(/bytes=(\d*)-(\d*)/);
    if (range) {
      const start = range[1] ? Number(range[1]) : 0;
      const end = range[2] ? Math.min(Number(range[2]), stat.size - 1) : stat.size - 1;
      reply
        .code(206)
        .header("Content-Range", `bytes ${start}-${end}/${stat.size}`)
        .header("Content-Length", end - start + 1);
      return reply.send(fs.createReadStream(file, { start, end }));
    }
    reply.header("Content-Length", stat.size);
    return reply.send(fs.createReadStream(file));
  });
}

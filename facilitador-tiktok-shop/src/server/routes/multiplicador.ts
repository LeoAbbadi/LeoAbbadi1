// Multiplicador: projetos, envio dos pedaços (gancho/corpo/CTA) e lotes de vídeos.
import crypto from "node:crypto";
import path from "node:path";
import type { FastifyInstance } from "fastify";
import { z } from "zod";
import { HttpError, effectivePlan, requireUser } from "../auth.ts";
import { one, query, tx } from "../db.ts";
import { storage } from "../storage/index.ts";
import { refund, reserve } from "../usage.ts";
import { planVideos, totalCombinations } from "../../shared/combos.ts";
import { MAX_CLIP_BYTES, PLANS, SLOT_LIMITS } from "../../shared/plans.ts";

type Slot = "hook" | "body" | "cta";

interface ClipRow {
  id: string;
  slot: Slot;
  label: string;
  original_name: string;
  storage_key: string;
  normalized_key: string | null;
  size_bytes: string;
  status: string;
  duration_s: number | null;
}

interface BatchRow {
  id: string;
  status: string;
  total: number;
  done: number;
  error: string | null;
  zip_key: string | null;
  zip_size_bytes: string | null;
  posts_per_day: number;
  start_date: string;
  created_at: string;
  finished_at: string | null;
  expires_at: string | null;
}

async function ownProject(userId: string, projectId: string) {
  const project = await one<{ id: string; name: string; product_name: string; created_at: string }>(
    "SELECT id, name, product_name, created_at FROM projects WHERE id = $1 AND user_id = $2",
    [projectId, userId],
  );
  if (!project) throw new HttpError(404, "Projeto não encontrado.");
  return project;
}

const uuid = z.string().uuid("Endereço inválido.");

export async function multiplicadorRoutes(app: FastifyInstance) {
  app.get("/api/projects", async (request) => {
    const user = await requireUser(request);
    return query(
      `SELECT p.id, p.name, p.product_name, p.created_at,
              (SELECT count(*) FROM clips c WHERE c.project_id = p.id AND c.status = 'ready')::int AS clips,
              (SELECT count(*) FROM outputs o JOIN batches b ON b.id = o.batch_id
                 WHERE b.project_id = p.id AND b.status = 'done')::int AS videos
         FROM projects p WHERE p.user_id = $1 ORDER BY p.created_at DESC`,
      [user.id],
    );
  });

  app.post("/api/projects", async (request) => {
    const user = await requireUser(request);
    const body = z
      .object({ name: z.string().trim().min(1, "Dê um nome ao projeto.").max(100), productName: z.string().trim().max(200).default("") })
      .parse(request.body);
    return one("INSERT INTO projects(user_id, name, product_name) VALUES ($1, $2, $3) RETURNING id, name, product_name", [
      user.id,
      body.name,
      body.productName,
    ]);
  });

  app.patch("/api/projects/:id", async (request) => {
    const user = await requireUser(request);
    const id = uuid.parse((request.params as { id: string }).id);
    await ownProject(user.id, id);
    const body = z
      .object({ name: z.string().trim().min(1).max(100).optional(), productName: z.string().trim().max(200).optional() })
      .parse(request.body);
    await query("UPDATE projects SET name = COALESCE($2, name), product_name = COALESCE($3, product_name) WHERE id = $1", [
      id,
      body.name ?? null,
      body.productName ?? null,
    ]);
    return { ok: true };
  });

  app.delete("/api/projects/:id", async (request) => {
    const user = await requireUser(request);
    const id = uuid.parse((request.params as { id: string }).id);
    await ownProject(user.id, id);
    const keys = await projectStorageKeys(id);
    await query("DELETE FROM projects WHERE id = $1", [id]);
    await storage.remove(keys);
    return { ok: true };
  });

  app.get("/api/projects/:id", async (request) => {
    const user = await requireUser(request);
    const id = uuid.parse((request.params as { id: string }).id);
    const project = await ownProject(user.id, id);
    const clips = await query<ClipRow>(
      `SELECT id, slot, label, original_name, storage_key, normalized_key, size_bytes, status, duration_s
         FROM clips WHERE project_id = $1 AND status = 'ready' ORDER BY created_at`,
      [id],
    );
    const batches = await query<BatchRow>(
      `SELECT id, status, total, done, error, zip_key, zip_size_bytes, posts_per_day, start_date, created_at, finished_at, expires_at
         FROM batches WHERE project_id = $1 ORDER BY created_at DESC`,
      [id],
    );
    return {
      project,
      clips: await Promise.all(
        clips.map(async (c) => ({
          id: c.id,
          slot: c.slot,
          label: c.label,
          name: c.original_name,
          sizeBytes: Number(c.size_bytes),
          durationS: c.duration_s,
          previewUrl: await storage.downloadUrl(c.storage_key),
        })),
      ),
      batches: batches.map(batchSummary),
    };
  });

  // ----- pedaços -----

  app.post("/api/projects/:id/clips", async (request) => {
    const user = await requireUser(request);
    const id = uuid.parse((request.params as { id: string }).id);
    await ownProject(user.id, id);
    const body = z
      .object({
        slot: z.enum(["hook", "body", "cta"]),
        filename: z.string().max(200),
        contentType: z.string().regex(/^video\//, "Envie um arquivo de vídeo."),
        size: z.number().int().positive().max(MAX_CLIP_BYTES, "Cada vídeo pode ter no máximo 300 MB."),
      })
      .parse(request.body);
    const count = await one<{ n: number }>(
      "SELECT count(*)::int AS n FROM clips WHERE project_id = $1 AND slot = $2 AND status = 'ready'",
      [id, body.slot],
    );
    if ((count?.n ?? 0) >= SLOT_LIMITS[body.slot]) {
      throw new HttpError(400, `Limite de ${SLOT_LIMITS[body.slot]} vídeos nesta caixa.`);
    }
    const ext = (path.extname(body.filename) || ".mp4").toLowerCase().replace(/[^.a-z0-9]/g, "");
    const key = `u/${user.id}/p/${id}/clips/${crypto.randomUUID()}${ext}`;
    const clip = await one<{ id: string }>(
      "INSERT INTO clips(project_id, slot, original_name, storage_key, size_bytes) VALUES ($1, $2, $3, $4, $5) RETURNING id",
      [id, body.slot, body.filename, key, body.size],
    );
    return { clipId: clip!.id, uploadUrl: await storage.uploadUrl(key, body.contentType) };
  });

  app.post("/api/clips/:id/complete", async (request) => {
    const user = await requireUser(request);
    const id = uuid.parse((request.params as { id: string }).id);
    const clip = await one<{ storage_key: string }>(
      `SELECT c.storage_key FROM clips c JOIN projects p ON p.id = c.project_id WHERE c.id = $1 AND p.user_id = $2`,
      [id, user.id],
    );
    if (!clip) throw new HttpError(404, "Vídeo não encontrado.");
    const size = await storage.size(clip.storage_key);
    if (!size) throw new HttpError(400, "O envio não terminou. Tente de novo.");
    if (size > MAX_CLIP_BYTES) {
      await storage.remove([clip.storage_key]);
      await query("DELETE FROM clips WHERE id = $1", [id]);
      throw new HttpError(400, "Cada vídeo pode ter no máximo 300 MB.");
    }
    await query("UPDATE clips SET status = 'ready', size_bytes = $2 WHERE id = $1", [id, size]);
    return { ok: true };
  });

  app.patch("/api/clips/:id", async (request) => {
    const user = await requireUser(request);
    const id = uuid.parse((request.params as { id: string }).id);
    const body = z.object({ label: z.string().max(300) }).parse(request.body);
    const rows = await query(
      `UPDATE clips c SET label = $3 FROM projects p WHERE c.id = $1 AND p.id = c.project_id AND p.user_id = $2 RETURNING c.id`,
      [id, user.id, body.label.trim()],
    );
    if (!rows.length) throw new HttpError(404, "Vídeo não encontrado.");
    return { ok: true };
  });

  app.delete("/api/clips/:id", async (request) => {
    const user = await requireUser(request);
    const id = uuid.parse((request.params as { id: string }).id);
    const clip = await one<{ storage_key: string; normalized_key: string | null }>(
      `SELECT c.storage_key, c.normalized_key FROM clips c JOIN projects p ON p.id = c.project_id WHERE c.id = $1 AND p.user_id = $2`,
      [id, user.id],
    );
    if (!clip) throw new HttpError(404, "Vídeo não encontrado.");
    const busy = await one(
      `SELECT 1 FROM outputs o JOIN batches b ON b.id = o.batch_id
        WHERE b.status IN ('queued', 'processing') AND $1 IN (o.hook_clip_id, o.body_clip_id, o.cta_clip_id) LIMIT 1`,
      [id],
    );
    if (busy) throw new HttpError(409, "Este vídeo está sendo usado num lote em andamento.");
    const outputKeys = await query<{ storage_key: string }>(
      `SELECT storage_key FROM outputs WHERE storage_key IS NOT NULL AND $1 IN (hook_clip_id, body_clip_id, cta_clip_id)`,
      [id],
    );
    await query("DELETE FROM clips WHERE id = $1", [id]);
    await storage.remove(
      [clip.storage_key, clip.normalized_key, ...outputKeys.map((o) => o.storage_key)].filter((k): k is string => !!k),
    );
    return { ok: true };
  });

  // ----- lotes -----

  app.post("/api/projects/:id/batches", async (request) => {
    const user = await requireUser(request);
    const id = uuid.parse((request.params as { id: string }).id);
    await ownProject(user.id, id);
    const plan = PLANS[effectivePlan(user)];
    const body = z
      .object({
        count: z.number().int().min(1),
        postsPerDay: z.number().int().min(1).max(10).default(1),
        startDate: z.string().regex(/^\d{4}-\d{2}-\d{2}$/).optional(),
      })
      .parse(request.body);

    const clips = await query<{ id: string; slot: Slot; label: string }>(
      "SELECT id, slot, label FROM clips WHERE project_id = $1 AND status = 'ready' ORDER BY created_at",
      [id],
    );
    const bySlot = (s: Slot) => clips.filter((c) => c.slot === s).map((c) => c.id);
    const hooks = bySlot("hook");
    const bodies = bySlot("body");
    const ctas = bySlot("cta");
    if (!hooks.length || !bodies.length || !ctas.length) {
      throw new HttpError(400, "Envie pelo menos 1 gancho, 1 corpo e 1 CTA.");
    }
    const possible = totalCombinations(hooks.length, bodies.length, ctas.length);
    const count = Math.min(body.count, possible, plan.maxVideosPerBatch);
    const running = await one("SELECT 1 FROM batches WHERE project_id = $1 AND status IN ('queued', 'processing')", [id]);
    if (running) throw new HttpError(409, "Já tem um lote sendo montado neste projeto. Aguarde terminar.");

    if (!(await reserve(user.id, plan.id, "videos", count))) {
      throw new HttpError(402, `Seu plano não tem cota para ${count} vídeos este mês. Gere menos vídeos ou mude de plano.`);
    }

    try {
      const project = await ownProject(user.id, id);
      const labels = new Map(clips.map((c) => [c.id, c.label]));
      const planned = planVideos(hooks, bodies, ctas, count, body.postsPerDay);
      const startDate = body.startDate ?? new Date().toISOString().slice(0, 10);

      const batchId = await tx(async (client) => {
        const res = await client.query<{ id: string }>(
          "INSERT INTO batches(project_id, user_id, total, posts_per_day, start_date) VALUES ($1, $2, $3, $4, $5) RETURNING id",
          [id, user.id, planned.length, body.postsPerDay, startDate],
        );
        const batch = res.rows[0]!.id;
        // insere tudo numa consulta só (até 250 linhas)
        const values: unknown[] = [];
        const tuples = planned.map((v, i) => {
          values.push(
            batch,
            v.position,
            v.hook,
            v.body,
            v.cta,
            v.label,
            v.originality,
            v.dayOffset,
            buildCaption(project.product_name, labels.get(v.hook) ?? ""),
          );
          const o = i * 9;
          return `($${o + 1}, $${o + 2}, $${o + 3}, $${o + 4}, $${o + 5}, $${o + 6}, $${o + 7}, $${startDateParam(planned.length)}::date + $${o + 8}::int, $${o + 9})`;
        });
        values.push(startDate);
        await client.query(
          `INSERT INTO outputs(batch_id, position, hook_clip_id, body_clip_id, cta_clip_id, label, originality, suggested_date, caption)
           VALUES ${tuples.join(", ")}`,
          values,
        );
        return batch;
      });
      return { batchId, total: planned.length };
    } catch (err) {
      await refund(user.id, "videos", count);
      throw err;
    }
  });

  app.get("/api/batches/:id", async (request) => {
    const user = await requireUser(request);
    const id = uuid.parse((request.params as { id: string }).id);
    const batch = await one<BatchRow & { project_id: string; project_name: string }>(
      `SELECT b.id, b.status, b.total, b.done, b.error, b.zip_key, b.zip_size_bytes, b.posts_per_day, b.start_date,
              b.created_at, b.finished_at, b.expires_at, b.project_id, p.name AS project_name
         FROM batches b JOIN projects p ON p.id = b.project_id WHERE b.id = $1 AND b.user_id = $2`,
      [id, user.id],
    );
    if (!batch) throw new HttpError(404, "Lote não encontrado.");
    const outputs = await query<{
      id: string;
      position: number;
      label: string;
      originality: number;
      suggested_date: string;
      caption: string;
      storage_key: string | null;
      size_bytes: string | null;
      duration_s: number | null;
      hook: string;
      body: string;
      cta: string;
      hook_label: string;
    }>(
      `SELECT o.id, o.position, o.label, o.originality, to_char(o.suggested_date, 'YYYY-MM-DD') AS suggested_date, o.caption,
              o.storage_key, o.size_bytes, o.duration_s,
              h.original_name AS hook, b.original_name AS body, c.original_name AS cta, h.label AS hook_label
         FROM outputs o
         JOIN clips h ON h.id = o.hook_clip_id
         JOIN clips b ON b.id = o.body_clip_id
         JOIN clips c ON c.id = o.cta_clip_id
        WHERE o.batch_id = $1 ORDER BY o.position`,
      [id],
    );
    const ready = batch.status === "done";
    return {
      batch: {
        ...batchSummary(batch),
        projectId: batch.project_id,
        projectName: batch.project_name,
        zipUrl: ready && batch.zip_key ? await storage.downloadUrl(batch.zip_key, `videos-${id.slice(0, 8)}.zip`) : null,
      },
      outputs: await Promise.all(
        outputs.map(async (o) => ({
          id: o.id,
          position: o.position,
          label: o.label,
          originality: o.originality,
          suggestedDate: o.suggested_date,
          caption: o.caption,
          parts: { hook: o.hook, body: o.body, cta: o.cta, hookText: o.hook_label },
          sizeBytes: o.size_bytes ? Number(o.size_bytes) : null,
          durationS: o.duration_s,
          url: ready && o.storage_key ? await storage.downloadUrl(o.storage_key) : null,
          downloadUrl:
            ready && o.storage_key
              ? await storage.downloadUrl(o.storage_key, `video-${String(o.position + 1).padStart(3, "0")}.mp4`)
              : null,
        })),
      ),
    };
  });

  app.patch("/api/outputs/:id", async (request) => {
    const user = await requireUser(request);
    const id = uuid.parse((request.params as { id: string }).id);
    const body = z.object({ caption: z.string().max(2200) }).parse(request.body);
    const rows = await query(
      `UPDATE outputs o SET caption = $3 FROM batches b WHERE o.id = $1 AND b.id = o.batch_id AND b.user_id = $2 RETURNING o.id`,
      [id, user.id, body.caption],
    );
    if (!rows.length) throw new HttpError(404, "Vídeo não encontrado.");
    return { ok: true };
  });
}

function startDateParam(count: number): number {
  return count * 9 + 1;
}

function batchSummary(b: BatchRow) {
  return {
    id: b.id,
    status: b.status,
    total: b.total,
    done: b.done,
    error: b.error,
    zipSizeBytes: b.zip_size_bytes ? Number(b.zip_size_bytes) : null,
    postsPerDay: b.posts_per_day,
    startDate: typeof b.start_date === "string" ? b.start_date : new Date(b.start_date).toISOString().slice(0, 10),
    createdAt: b.created_at,
    finishedAt: b.finished_at,
    expiresAt: b.expires_at,
  };
}

/** Legenda inicial do post: texto do gancho + hashtags do produto. O usuário pode editar. */
export function buildCaption(productName: string, hookText: string): string {
  const tags = ["#tiktokshop", "#achadinhos"];
  const productTag = productName
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .toLowerCase()
    .split(/\s+/)
    .slice(0, 3)
    .join("")
    .replace(/[^a-z0-9]/g, "");
  if (productTag) tags.unshift(`#${productTag}`);
  return [hookText.trim(), tags.join(" ")].filter(Boolean).join("\n\n");
}

async function projectStorageKeys(projectId: string): Promise<string[]> {
  const rows = await query<{ key: string }>(
    `SELECT storage_key AS key FROM clips WHERE project_id = $1
     UNION ALL SELECT normalized_key FROM clips WHERE project_id = $1 AND normalized_key IS NOT NULL
     UNION ALL SELECT o.storage_key FROM outputs o JOIN batches b ON b.id = o.batch_id WHERE b.project_id = $1 AND o.storage_key IS NOT NULL
     UNION ALL SELECT zip_key FROM batches WHERE project_id = $1 AND zip_key IS NOT NULL`,
    [projectId],
  );
  return rows.map((r) => r.key);
}

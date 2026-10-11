// Worker de vídeo: pega lotes da fila (tabela batches), monta os vídeos com FFmpeg
// e sobe o resultado para o armazenamento. Pode rodar em quantas máquinas quiser:
// cada lote é travado com FOR UPDATE SKIP LOCKED, então dois workers nunca pegam o mesmo.
import fs from "node:fs";
import fsp from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { ZipArchive } from "archiver";
import { config } from "../server/config.ts";
import { one, pool, query } from "../server/db.ts";
import { migrate } from "../server/migrate.ts";
import { storage } from "../server/storage/index.ts";
import { refund } from "../server/usage.ts";
import { LABEL_INFO, type OriginalityLabel } from "../shared/combos.ts";
import { concat, normalize, probe } from "./ffmpeg.ts";

const POLL_MS = 3000;
const STALE_MINUTES = 15;
const MAX_ATTEMPTS = 3;

interface Batch {
  id: string;
  user_id: string;
  project_id: string;
  total: number;
  attempts: number;
  created_at: Date;
}

async function claimBatch(): Promise<Batch | undefined> {
  return one<Batch>(
    `UPDATE batches SET status = 'processing', locked_at = now(), started_at = COALESCE(started_at, now()), attempts = attempts + 1
      WHERE id = (
        SELECT id FROM batches
         WHERE status = 'queued' OR (status = 'processing' AND locked_at < now() - interval '${STALE_MINUTES} minutes')
         ORDER BY created_at FOR UPDATE SKIP LOCKED LIMIT 1)
      RETURNING id, user_id, project_id, total, attempts, created_at`,
  );
}

async function processBatch(batch: Batch): Promise<void> {
  const work = await fsp.mkdtemp(path.join(os.tmpdir(), `lote-${batch.id.slice(0, 8)}-`));
  const heartbeat = setInterval(() => {
    query("UPDATE batches SET locked_at = now() WHERE id = $1", [batch.id]).catch(() => {});
  }, 60_000);
  try {
    const outputs = await query<{
      id: string;
      position: number;
      hook_clip_id: string;
      body_clip_id: string;
      cta_clip_id: string;
      label: OriginalityLabel;
      suggested_date: string;
      caption: string;
      storage_key: string | null;
    }>(
      `SELECT id, position, hook_clip_id, body_clip_id, cta_clip_id, label, to_char(suggested_date, 'DD/MM/YYYY') AS suggested_date,
              caption, storage_key
         FROM outputs WHERE batch_id = $1 ORDER BY position`,
      [batch.id],
    );

    // 1) padroniza cada pedaço usado (só na primeira vez; depois reaproveita)
    const clipIds = [...new Set(outputs.flatMap((o) => [o.hook_clip_id, o.body_clip_id, o.cta_clip_id]))];
    const localClip = new Map<string, string>();
    for (const clipId of clipIds) {
      const clip = await one<{ storage_key: string; normalized_key: string | null; project_id: string }>(
        "SELECT storage_key, normalized_key, project_id FROM clips WHERE id = $1",
        [clipId],
      );
      if (!clip) throw new Error("Um dos pedaços foi apagado durante o processamento.");
      const normalizedLocal = path.join(work, `n-${clipId}.mp4`);
      if (clip.normalized_key) {
        await storage.getFile(clip.normalized_key, normalizedLocal);
      } else {
        const raw = path.join(work, `raw-${clipId}`);
        await storage.getFile(clip.storage_key, raw);
        const info = await normalize(raw, normalizedLocal);
        await fsp.rm(raw, { force: true });
        const key = clip.storage_key.replace(/\/clips\/([^/]+)$/, "/normalized/$1").replace(/\.[a-z0-9]+$/i, "") + ".mp4";
        await storage.putFile(key, normalizedLocal, "video/mp4");
        await query("UPDATE clips SET normalized_key = $2, duration_s = $3 WHERE id = $1", [clipId, key, info.duration]);
      }
      localClip.set(clipId, normalizedLocal);
    }

    // 2) junta gancho + corpo + CTA de cada vídeo (cópia, sem recodificar)
    const outDir = path.join(work, "out");
    await fsp.mkdir(outDir);
    const fileFor = (position: number) => path.join(outDir, `video-${String(position + 1).padStart(3, "0")}.mp4`);
    const list = path.join(work, "list.txt");
    for (const o of outputs) {
      const file = fileFor(o.position);
      if (o.storage_key) {
        await storage.getFile(o.storage_key, file);
        continue;
      }
      await concat(
        [localClip.get(o.hook_clip_id)!, localClip.get(o.body_clip_id)!, localClip.get(o.cta_clip_id)!],
        file,
        list,
      );
      const info = await probe(file);
      const size = (await fsp.stat(file)).size;
      const key = `u/${batch.user_id}/p/${batch.project_id}/lotes/${batch.id}/${path.basename(file)}`;
      await storage.putFile(key, file, "video/mp4");
      await query("UPDATE outputs SET storage_key = $2, size_bytes = $3, duration_s = $4 WHERE id = $1", [
        o.id,
        key,
        size,
        info.duration,
      ]);
      await query("UPDATE batches SET done = done + 1 WHERE id = $1", [batch.id]);
    }

    // 3) ZIP com todos os vídeos + planilha com a ordem de postagem e as legendas
    const csv = [
      "ordem;data sugerida;selo;dica;arquivo;legenda",
      ...outputs.map((o) =>
        [
          o.position + 1,
          o.suggested_date,
          LABEL_INFO[o.label].title,
          LABEL_INFO[o.label].tip,
          path.basename(fileFor(o.position)),
          `"${o.caption.replace(/"/g, '""')}"`,
        ].join(";"),
      ),
    ].join("\n");
    const zipPath = path.join(work, "videos.zip");
    await new Promise<void>((resolve, reject) => {
      const zip = new ZipArchive({ store: true });
      const out = fs.createWriteStream(zipPath);
      out.on("close", resolve);
      zip.on("error", reject);
      zip.pipe(out);
      zip.append("﻿" + csv, { name: "ordem-de-postagem.csv" });
      for (const o of outputs) zip.file(fileFor(o.position), { name: path.basename(fileFor(o.position)) });
      void zip.finalize();
    });
    const zipKey = `u/${batch.user_id}/p/${batch.project_id}/lotes/${batch.id}/videos.zip`;
    await storage.putFile(zipKey, zipPath, "application/zip");

    await query(
      `UPDATE batches SET status = 'done', done = total, zip_key = $2, zip_size_bytes = $3, finished_at = now(),
              expires_at = now() + ($4 || ' days')::interval, error = NULL
        WHERE id = $1`,
      [batch.id, zipKey, (await fsp.stat(zipPath)).size, String(config.outputRetentionDays)],
    );
  } finally {
    clearInterval(heartbeat);
    await fsp.rm(work, { recursive: true, force: true });
  }
}

async function failBatch(batch: Batch, err: Error): Promise<void> {
  console.error(`[lote ${batch.id}] erro na tentativa ${batch.attempts}:`, err.message);
  if (batch.attempts < MAX_ATTEMPTS) {
    await query("UPDATE batches SET status = 'queued', locked_at = NULL WHERE id = $1", [batch.id]);
    return;
  }
  const row = await one<{ done: number }>(
    "UPDATE batches SET status = 'error', error = $2, finished_at = now() WHERE id = $1 RETURNING done",
    [batch.id, "Não conseguimos montar os vídeos. Confira se os arquivos abrem no celular e tente de novo."],
  );
  // devolve a cota dos vídeos que não foram entregues, no mês em que foi cobrada
  await refund(batch.user_id, "videos", batch.total - (row?.done ?? 0), batch.created_at.toISOString().slice(0, 7));
}

/** Apaga os vídeos de lotes vencidos. Os pedaços originais ficam enquanto o projeto existir. */
async function cleanupExpired(): Promise<void> {
  const expired = await query<{ id: string; zip_key: string | null }>(
    "SELECT id, zip_key FROM batches WHERE status = 'done' AND expires_at < now() LIMIT 50",
  );
  for (const b of expired) {
    const keys = await query<{ storage_key: string }>(
      "SELECT storage_key FROM outputs WHERE batch_id = $1 AND storage_key IS NOT NULL",
      [b.id],
    );
    await storage.remove([...keys.map((k) => k.storage_key), ...(b.zip_key ? [b.zip_key] : [])]);
    await query("UPDATE outputs SET storage_key = NULL WHERE batch_id = $1", [b.id]);
    await query("UPDATE batches SET status = 'expired', zip_key = NULL WHERE id = $1", [b.id]);
  }
  // envios que nunca terminaram
  const stale = await query<{ id: string; storage_key: string }>(
    "DELETE FROM clips WHERE status = 'uploading' AND created_at < now() - interval '1 day' RETURNING id, storage_key",
  );
  await storage.remove(stale.map((s) => s.storage_key));
}

let stopping = false;

async function loop(slot: number): Promise<void> {
  while (!stopping) {
    const batch = await claimBatch().catch((err) => {
      console.error("erro ao buscar fila:", err.message);
      return undefined;
    });
    if (!batch) {
      await new Promise((r) => setTimeout(r, POLL_MS));
      continue;
    }
    const started = Date.now();
    console.log(`[worker ${slot}] lote ${batch.id}: ${batch.total} vídeos`);
    try {
      await processBatch(batch);
      console.log(`[worker ${slot}] lote ${batch.id} pronto em ${((Date.now() - started) / 1000).toFixed(1)}s`);
    } catch (err) {
      await failBatch(batch, err as Error).catch((e) => console.error(e));
    }
  }
}

if (import.meta.url === `file://${process.argv[1]}`) {
  await migrate();
  const timer = setInterval(() => cleanupExpired().catch((e) => console.error("limpeza:", e.message)), 10 * 60_000);
  void cleanupExpired().catch(() => {});
  const shutdown = () => {
    stopping = true;
    clearInterval(timer);
    console.log("Encerrando worker depois do lote atual...");
  };
  process.on("SIGTERM", shutdown);
  process.on("SIGINT", shutdown);
  console.log(`Worker de vídeo iniciado (${config.workerConcurrency} em paralelo).`);
  await Promise.all(Array.from({ length: Math.max(1, config.workerConcurrency) }, (_, i) => loop(i + 1)));
  await pool.end();
}

export { processBatch, claimBatch, cleanupExpired };

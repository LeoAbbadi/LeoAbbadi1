// Aplica os arquivos de db/migrations em ordem, uma vez cada.
// Usa uma trava do Postgres para a API e o worker poderem subir ao mesmo tempo.
import fs from "node:fs/promises";
import path from "node:path";
import { pool } from "./db.ts";

const LOCK_ID = 7_270_201;

export async function migrate(): Promise<string[]> {
  const dir = path.resolve("db/migrations");
  const files = (await fs.readdir(dir)).filter((f) => f.endsWith(".sql")).sort();
  const client = await pool.connect();
  const applied: string[] = [];
  try {
    await client.query("SELECT pg_advisory_lock($1)", [LOCK_ID]);
    await client.query(
      "CREATE TABLE IF NOT EXISTS schema_migrations (name text PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now())",
    );
    const done = new Set((await client.query<{ name: string }>("SELECT name FROM schema_migrations")).rows.map((r) => r.name));
    for (const file of files) {
      if (done.has(file)) continue;
      const sql = await fs.readFile(path.join(dir, file), "utf8");
      try {
        await client.query("BEGIN");
        await client.query(sql);
        await client.query("INSERT INTO schema_migrations(name) VALUES ($1)", [file]);
        await client.query("COMMIT");
        applied.push(file);
      } catch (err) {
        await client.query("ROLLBACK");
        throw new Error(`Falha na migração ${file}: ${(err as Error).message}`);
      }
    }
  } finally {
    await client.query("SELECT pg_advisory_unlock($1)", [LOCK_ID]).catch(() => {});
    client.release();
  }
  return applied;
}

if (import.meta.url === `file://${process.argv[1]}`) {
  migrate()
    .then((applied) => {
      console.log(applied.length ? `Migrações aplicadas: ${applied.join(", ")}` : "Banco já está atualizado.");
      return pool.end();
    })
    .catch((err) => {
      console.error(err);
      process.exit(1);
    });
}

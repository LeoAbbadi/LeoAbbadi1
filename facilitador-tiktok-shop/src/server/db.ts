import pg from "pg";
import { config } from "./config.ts";

export const pool = new pg.Pool({
  connectionString: config.databaseUrl,
  max: 10,
  ssl: /sslmode=require|supabase|neon|railway/.test(config.databaseUrl) ? { rejectUnauthorized: false } : undefined,
});

export async function query<T extends pg.QueryResultRow = Record<string, unknown>>(
  sql: string,
  params: unknown[] = [],
): Promise<T[]> {
  const res = await pool.query<T>(sql, params);
  return res.rows;
}

export async function one<T extends pg.QueryResultRow = Record<string, unknown>>(
  sql: string,
  params: unknown[] = [],
): Promise<T | undefined> {
  const rows = await query<T>(sql, params);
  return rows[0];
}

export async function tx<T>(fn: (client: pg.PoolClient) => Promise<T>): Promise<T> {
  const client = await pool.connect();
  try {
    await client.query("BEGIN");
    const result = await fn(client);
    await client.query("COMMIT");
    return result;
  } catch (err) {
    await client.query("ROLLBACK");
    throw err;
  } finally {
    client.release();
  }
}

export function currentPeriod(date = new Date()): string {
  return date.toISOString().slice(0, 7);
}

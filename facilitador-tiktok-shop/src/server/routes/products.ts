// Pesquisa de produtos do TikTok Shop: ranking por faturamento, tendências 24h e vídeos que venderam.
// Os dados entram por importação CSV (área admin) ou por um provedor de dados: veja docs/DADOS.md.
import type { FastifyInstance } from "fastify";
import { z } from "zod";
import { HttpError, effectivePlan, isAdmin, requireUser } from "../auth.ts";
import { one, query, tx } from "../db.ts";
import { PLANS } from "../../shared/plans.ts";

const listQuery = z.object({
  country: z.enum(["BR", "US"]).default("BR"),
  period: z.enum(["1d", "7d", "30d"]).default("7d"),
  sort: z.enum(["gmv", "sales", "growth"]).default("gmv"),
  category: z.string().max(100).optional(),
  q: z.string().max(100).optional(),
  minCommission: z.coerce.number().min(0).max(100).optional(),
  limit: z.coerce.number().int().min(1).max(100).default(50),
  offset: z.coerce.number().int().min(0).default(0),
});

export async function productRoutes(app: FastifyInstance) {
  app.get("/api/products", async (request) => {
    const user = await requireUser(request);
    const plan = PLANS[effectivePlan(user)];
    const f = listQuery.parse(request.query);
    if (!plan.countries.includes(f.country)) {
      throw new HttpError(402, "Os produtos dos EUA fazem parte do plano Pro.");
    }
    const freeCap = plan.id === "free" ? 10 : Infinity;
    const limit = Math.min(f.limit, Math.max(0, freeCap - f.offset));
    if (limit === 0) return { items: [], locked: true };

    const where = ["country = $1"];
    const params: unknown[] = [f.country];
    if (f.category) {
      params.push(f.category);
      where.push(`category = $${params.length}`);
    }
    if (f.q) {
      params.push(`%${f.q}%`);
      where.push(`(name ILIKE $${params.length} OR shop_name ILIKE $${params.length})`);
    }
    if (f.minCommission !== undefined) {
      params.push(f.minCommission);
      where.push(`commission_pct >= $${params.length}`);
    }
    const order =
      f.sort === "growth" ? "growth_pct_1d" : f.sort === "sales" ? `sales_${f.period}` : `gmv_cents_${f.period}`;
    params.push(user.id, limit, f.offset);
    const items = await query(
      `SELECT p.id, p.name, p.category, p.shop_name, p.image_url, p.product_url, p.price_cents, p.commission_pct,
              p.sales_${f.period} AS sales, p.gmv_cents_${f.period} AS gmv_cents, p.growth_pct_1d, p.creators_count,
              p.is_sample, p.updated_at,
              EXISTS (SELECT 1 FROM favorites fav WHERE fav.product_id = p.id AND fav.user_id = $${params.length - 2}) AS favorite
         FROM products p
        WHERE ${where.join(" AND ")}
        ORDER BY ${order} DESC, p.name
        LIMIT $${params.length - 1} OFFSET $${params.length}`,
      params,
    );
    return { items, locked: plan.id === "free" && f.offset + items.length >= freeCap };
  });

  app.get("/api/products/categories", async (request) => {
    await requireUser(request);
    const rows = await query<{ category: string }>(
      "SELECT DISTINCT category FROM products WHERE category <> '' ORDER BY category",
    );
    return rows.map((r) => r.category);
  });

  app.get("/api/products/:id", async (request) => {
    const user = await requireUser(request);
    const id = z.string().uuid().parse((request.params as { id: string }).id);
    const product = await one<{ country: "BR" | "US" }>(
      `SELECT p.*, EXISTS (SELECT 1 FROM favorites f WHERE f.product_id = p.id AND f.user_id = $2) AS favorite
         FROM products p WHERE p.id = $1`,
      [id, user.id],
    );
    if (!product) throw new HttpError(404, "Produto não encontrado.");
    if (!PLANS[effectivePlan(user)].countries.includes(product.country)) {
      throw new HttpError(402, "Os produtos dos EUA fazem parte do plano Pro.");
    }
    const videos = await query(
      "SELECT creator_handle, video_url, views, gmv_cents, posted_at FROM product_videos WHERE product_id = $1 ORDER BY views DESC LIMIT 20",
      [id],
    );
    return { product, videos };
  });

  app.get("/api/favorites", async (request) => {
    const user = await requireUser(request);
    return query(
      `SELECT p.id, p.name, p.category, p.image_url, p.price_cents, p.gmv_cents_7d AS gmv_cents, p.growth_pct_1d, p.country
         FROM favorites f JOIN products p ON p.id = f.product_id WHERE f.user_id = $1 ORDER BY f.created_at DESC`,
      [user.id],
    );
  });

  app.put("/api/favorites/:id", async (request) => {
    const user = await requireUser(request);
    const id = z.string().uuid().parse((request.params as { id: string }).id);
    await query("INSERT INTO favorites(user_id, product_id) VALUES ($1, $2) ON CONFLICT DO NOTHING", [user.id, id]);
    return { ok: true };
  });

  app.delete("/api/favorites/:id", async (request) => {
    const user = await requireUser(request);
    const id = z.string().uuid().parse((request.params as { id: string }).id);
    await query("DELETE FROM favorites WHERE user_id = $1 AND product_id = $2", [user.id, id]);
    return { ok: true };
  });

  // ----- admin: importação de CSV -----
  app.post("/api/admin/products/import", async (request) => {
    const user = await requireUser(request);
    if (!isAdmin(user)) throw new HttpError(403, "Só administradores.");
    const body = z
      .object({ csv: z.string().min(1).max(20_000_000), source: z.string().max(50).default("csv"), replaceSamples: z.boolean().default(true) })
      .parse(request.body);
    const rows = parseProductCsv(body.csv);
    await tx(async (client) => {
      if (body.replaceSamples) await client.query("DELETE FROM products WHERE is_sample");
      for (const r of rows) {
        await client.query(
          `INSERT INTO products(source, external_id, country, name, category, shop_name, image_url, product_url, price_cents,
              commission_pct, sales_1d, sales_7d, sales_30d, gmv_cents_1d, gmv_cents_7d, gmv_cents_30d, growth_pct_1d, creators_count, updated_at)
           VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18, now())
           ON CONFLICT (source, external_id, country) DO UPDATE SET
              name = EXCLUDED.name, category = EXCLUDED.category, shop_name = EXCLUDED.shop_name, image_url = EXCLUDED.image_url,
              product_url = EXCLUDED.product_url, price_cents = EXCLUDED.price_cents, commission_pct = EXCLUDED.commission_pct,
              sales_1d = EXCLUDED.sales_1d, sales_7d = EXCLUDED.sales_7d, sales_30d = EXCLUDED.sales_30d,
              gmv_cents_1d = EXCLUDED.gmv_cents_1d, gmv_cents_7d = EXCLUDED.gmv_cents_7d, gmv_cents_30d = EXCLUDED.gmv_cents_30d,
              growth_pct_1d = EXCLUDED.growth_pct_1d, creators_count = EXCLUDED.creators_count, updated_at = now()`,
          [
            body.source,
            r.external_id,
            r.country,
            r.name,
            r.category,
            r.shop_name,
            r.image_url,
            r.product_url,
            r.price_cents,
            r.commission_pct,
            r.sales_1d,
            r.sales_7d,
            r.sales_30d,
            r.gmv_cents_1d,
            r.gmv_cents_7d,
            r.gmv_cents_30d,
            growthPct(r.sales_1d, r.sales_7d),
            r.creators_count,
          ],
        );
      }
    });
    return { imported: rows.length };
  });
}

export function growthPct(sales1d: number, sales7d: number): number {
  const avg = sales7d / 7;
  if (avg <= 0) return sales1d > 0 ? 100 : 0;
  return Math.round(((sales1d - avg) / avg) * 1000) / 10;
}

// ----- CSV -----

export const CSV_COLUMNS = [
  "external_id",
  "country",
  "name",
  "category",
  "shop_name",
  "image_url",
  "product_url",
  "price",
  "commission_pct",
  "sales_1d",
  "sales_7d",
  "sales_30d",
  "gmv_1d",
  "gmv_7d",
  "gmv_30d",
  "creators_count",
] as const;

export function parseCsv(text: string): string[][] {
  const rows: string[][] = [];
  let row: string[] = [];
  let field = "";
  let quoted = false;
  const sep = text.split("\n", 1)[0]!.includes(";") ? ";" : ",";
  for (let i = 0; i < text.length; i++) {
    const ch = text[i]!;
    if (quoted) {
      if (ch === '"' && text[i + 1] === '"') {
        field += '"';
        i++;
      } else if (ch === '"') quoted = false;
      else field += ch;
    } else if (ch === '"') quoted = true;
    else if (ch === sep) {
      row.push(field);
      field = "";
    } else if (ch === "\n" || ch === "\r") {
      if (ch === "\r" && text[i + 1] === "\n") i++;
      row.push(field);
      field = "";
      if (row.some((c) => c.trim() !== "")) rows.push(row);
      row = [];
    } else field += ch;
  }
  row.push(field);
  if (row.some((c) => c.trim() !== "")) rows.push(row);
  return rows;
}

/** Aceita "1.234,56" (BR) e "1234.56" */
function num(v: string | undefined): number {
  if (!v) return 0;
  const s = v.trim().replace(/[^\d.,-]/g, "");
  const normalized = s.includes(",") ? s.replace(/\./g, "").replace(",", ".") : s;
  const n = Number(normalized);
  return Number.isFinite(n) ? n : 0;
}

export function parseProductCsv(text: string) {
  const [header, ...lines] = parseCsv(text.replace(/^﻿/, ""));
  if (!header) throw new HttpError(400, "CSV vazio.");
  const idx = new Map(header.map((h, i) => [h.trim().toLowerCase(), i]));
  for (const col of ["external_id", "name"]) {
    if (!idx.has(col)) throw new HttpError(400, `Coluna obrigatória faltando: ${col}. Colunas aceitas: ${CSV_COLUMNS.join(", ")}`);
  }
  const get = (line: string[], col: (typeof CSV_COLUMNS)[number]) => {
    const i = idx.get(col);
    return i === undefined ? "" : (line[i] ?? "").trim();
  };
  return lines.map((line, n) => {
    const country = (get(line, "country") || "BR").toUpperCase();
    if (country !== "BR" && country !== "US") throw new HttpError(400, `Linha ${n + 2}: país deve ser BR ou US.`);
    const name = get(line, "name");
    const externalId = get(line, "external_id");
    if (!name || !externalId) throw new HttpError(400, `Linha ${n + 2}: external_id e name são obrigatórios.`);
    return {
      external_id: externalId,
      country,
      name,
      category: get(line, "category"),
      shop_name: get(line, "shop_name"),
      image_url: get(line, "image_url"),
      product_url: get(line, "product_url"),
      price_cents: Math.round(num(get(line, "price")) * 100),
      commission_pct: num(get(line, "commission_pct")),
      sales_1d: Math.round(num(get(line, "sales_1d"))),
      sales_7d: Math.round(num(get(line, "sales_7d"))),
      sales_30d: Math.round(num(get(line, "sales_30d"))),
      gmv_cents_1d: Math.round(num(get(line, "gmv_1d")) * 100),
      gmv_cents_7d: Math.round(num(get(line, "gmv_7d")) * 100),
      gmv_cents_30d: Math.round(num(get(line, "gmv_30d")) * 100),
      creators_count: Math.round(num(get(line, "creators_count"))),
    };
  });
}

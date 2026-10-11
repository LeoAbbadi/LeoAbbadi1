// Dados de EXEMPLO para desenvolvimento: produtos fictícios (marcados com is_sample)
// e uma conta de teste. Em produção os produtos vêm do provedor de dados (docs/DADOS.md).
import { hashPassword } from "./auth.ts";
import { pool, query } from "./db.ts";
import { migrate } from "./migrate.ts";
import { sampleProducts } from "../shared/samples.ts";

async function main() {
  await migrate();
  await query("DELETE FROM products WHERE is_sample");

  const products = sampleProducts();
  for (const p of products) {
    const [row] = await query<{ id: string }>(
      `INSERT INTO products(source, external_id, country, name, category, shop_name, price_cents, commission_pct,
          sales_1d, sales_7d, sales_30d, gmv_cents_1d, gmv_cents_7d, gmv_cents_30d, growth_pct_1d, creators_count, is_sample)
       VALUES ('exemplo', $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, true) RETURNING id`,
      [
        p.external_id, p.country, p.name, p.category, p.shop_name, p.price_cents, p.commission_pct,
        p.sales_1d, p.sales_7d, p.sales_30d, p.gmv_cents_1d, p.gmv_cents_7d, p.gmv_cents_30d, p.growth_pct_1d, p.creators_count,
      ],
    );
    for (const v of p.videos) {
      await query(
        `INSERT INTO product_videos(product_id, creator_handle, views, gmv_cents, posted_at)
         VALUES ($1, $2, $3, $4, CURRENT_DATE - $5::int)`,
        [row!.id, v.creator_handle, v.views, v.gmv_cents, v.days_ago],
      );
    }
  }
  const n = products.length;

  const email = "demo@facilitador.local";
  await query(
    `INSERT INTO users(email, name, password_hash, plan, plan_period, plan_status)
     VALUES ($1, 'Conta de teste', $2, 'pro', 'monthly', 'active') ON CONFLICT (email) DO NOTHING`,
    [email, await hashPassword("demo12345")],
  );
  console.log(`${n} produtos de exemplo criados. Conta de teste: ${email} / demo12345`);
  await pool.end();
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});

// Dados de EXEMPLO para desenvolvimento: produtos fictícios (marcados com is_sample)
// e uma conta de teste. Em produção os produtos vêm do provedor de dados (docs/DADOS.md).
import { hashPassword } from "./auth.ts";
import { pool, query } from "./db.ts";
import { migrate } from "./migrate.ts";
import { growthPct } from "./routes/products.ts";

const CATALOG: Record<string, string[]> = {
  "Beleza e cuidados": [
    "Sérum facial vitamina C 30ml",
    "Kit skincare 5 passos",
    "Escova secadora 3 em 1",
    "Máscara de cílios à prova d'água",
    "Protetor solar com cor FPS 50",
    "Perfume árabe 100ml",
  ],
  "Casa e cozinha": [
    "Mini processador elétrico recarregável",
    "Organizador de geladeira 6 peças",
    "Mop giratório com balde",
    "Garrafa térmica 1L inox",
    "Luminária LED sensor de presença",
    "Air fryer 4L digital",
  ],
  "Moda feminina": [
    "Legging cintura alta modeladora",
    "Conjunto fitness seamless",
    "Body canelado manga longa",
    "Calça pantalona alfaiataria",
    "Bolsa transversal couro sintético",
  ],
  Eletrônicos: [
    "Fone bluetooth com cancelamento de ruído",
    "Mini projetor portátil HD",
    "Smartwatch tela AMOLED",
    "Carregador portátil 20.000mAh",
    "Ring light de mesa com tripé",
  ],
  "Saúde e bem-estar": [
    "Massageador elétrico de pescoço",
    "Garrafa motivacional 2L",
    "Faixa elástica kit 5 intensidades",
    "Escova de dentes elétrica sônica",
  ],
  Infantil: ["Kit massinha 12 cores", "Mordedor de silicone", "Luminária projetor de estrelas"],
  Pet: ["Escova removedora de pelos", "Fonte de água para gatos", "Cama pet nuvem antiestresse"],
};

// gerador pseudoaleatório fixo para os números serem sempre os mesmos
let seed = 20261011;
const rand = () => ((seed = (seed * 1664525 + 1013904223) % 4294967296) / 4294967296);
const between = (a: number, b: number) => Math.round(a + rand() * (b - a));

async function main() {
  await migrate();
  await query("DELETE FROM products WHERE is_sample");

  let n = 0;
  for (const country of ["BR", "US"] as const) {
    for (const [category, names] of Object.entries(CATALOG)) {
      for (const name of names) {
        if (country === "US" && rand() < 0.5) continue;
        n++;
        const price = country === "BR" ? between(25, 260) : between(9, 70);
        const sales7d = between(300, 22000);
        const trend = 0.4 + rand() * 3.2;
        const sales1d = Math.round((sales7d / 7) * trend);
        const sales30d = Math.round(sales7d * (3.2 + rand() * 1.4));
        const [product] = await query<{ id: string }>(
          `INSERT INTO products(source, external_id, country, name, category, shop_name, price_cents, commission_pct,
              sales_1d, sales_7d, sales_30d, gmv_cents_1d, gmv_cents_7d, gmv_cents_30d, growth_pct_1d, creators_count, is_sample)
           VALUES ('exemplo', $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, true) RETURNING id`,
          [
            `ex-${country}-${n}`,
            country,
            country === "US" ? `${name} (EUA)` : name,
            category,
            `Loja Exemplo ${between(1, 30)}`,
            price * 100,
            between(5, 25),
            sales1d,
            sales7d,
            sales30d,
            sales1d * price * 100,
            sales7d * price * 100,
            sales30d * price * 100,
            growthPct(sales1d, sales7d),
            between(5, 400),
          ],
        );
        const videos = between(2, 5);
        for (let v = 0; v < videos; v++) {
          await query(
            `INSERT INTO product_videos(product_id, creator_handle, views, gmv_cents, posted_at)
             VALUES ($1, $2, $3, $4, CURRENT_DATE - $5::int)`,
            [product!.id, `@criador_exemplo${between(1, 99)}`, between(20_000, 9_000_000), between(500, 90_000) * 100, between(0, 20)],
          );
        }
      }
    }
  }

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

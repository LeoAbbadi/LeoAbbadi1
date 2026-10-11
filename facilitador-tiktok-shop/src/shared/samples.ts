// Dados de EXEMPLO usados no desenvolvimento (seed do banco) e na demonstração que
// roda só no navegador. Os números são fictícios e os produtos vêm marcados como exemplo.

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

export interface SampleProduct {
  external_id: string;
  country: "BR" | "US";
  name: string;
  category: string;
  shop_name: string;
  price_cents: number;
  commission_pct: number;
  sales_1d: number;
  sales_7d: number;
  sales_30d: number;
  gmv_cents_1d: number;
  gmv_cents_7d: number;
  gmv_cents_30d: number;
  growth_pct_1d: number;
  creators_count: number;
  videos: { creator_handle: string; views: number; gmv_cents: number; days_ago: number }[];
}

export function growthPct(sales1d: number, sales7d: number): number {
  const avg = sales7d / 7;
  if (avg <= 0) return sales1d > 0 ? 100 : 0;
  return Math.round(((sales1d - avg) / avg) * 1000) / 10;
}

/** Sempre gera a mesma lista (gerador pseudoaleatório com semente fixa). */
export function sampleProducts(): SampleProduct[] {
  let seed = 20261011;
  const rand = () => (seed = (seed * 1664525 + 1013904223) % 4294967296) / 4294967296;
  const between = (a: number, b: number) => Math.round(a + rand() * (b - a));
  const out: SampleProduct[] = [];
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
        out.push({
          external_id: `ex-${country}-${n}`,
          country,
          name: country === "US" ? `${name} (EUA)` : name,
          category,
          shop_name: `Loja Exemplo ${between(1, 30)}`,
          price_cents: price * 100,
          commission_pct: between(5, 25),
          sales_1d: sales1d,
          sales_7d: sales7d,
          sales_30d: sales30d,
          gmv_cents_1d: sales1d * price * 100,
          gmv_cents_7d: sales7d * price * 100,
          gmv_cents_30d: sales30d * price * 100,
          growth_pct_1d: growthPct(sales1d, sales7d),
          creators_count: between(5, 400),
          videos: Array.from({ length: between(2, 5) }, () => ({
            creator_handle: `@criador_exemplo${between(1, 99)}`,
            views: between(20_000, 9_000_000),
            gmv_cents: between(500, 90_000) * 100,
            days_ago: between(0, 20),
          })),
        });
      }
    }
  }
  return out;
}

// ---------- roteiros de exemplo (sem chave da IA) ----------

export interface SampleScriptInput {
  kind: "videos" | "live";
  productName: string;
  liveMinutes: number;
}

export function sampleScript(input: SampleScriptInput) {
  const p = input.productName;
  if (input.kind === "videos") {
    return {
      hooks: [
        { text: `Ninguém me contou isso antes de eu comprar ${p}…`, technique: "curiosidade" },
        { text: `Se você sofre com isso todo dia, para tudo e olha.`, technique: "dor" },
        { text: `Vou falar o que ninguém fala sobre ${p}.`, technique: "polêmica leve" },
        { text: `Olha o que acontece em 5 segundos.`, technique: "prova visual" },
        { text: `Você sabia que dá pra resolver isso sem gastar muito?`, technique: "pergunta" },
        { text: `3 motivos pra eu não largar mais ${p}.`, technique: "lista" },
        { text: `Antes e depois. Sem filtro.`, technique: "antes e depois" },
        { text: `O segredo que as lojas não contam.`, technique: "segredo" },
        { text: `Acabou da última vez em 2 dias. Voltou.`, technique: "urgência" },
        { text: `Se você é igual a mim e não tem tempo, isso é pra você.`, technique: "identificação" },
      ],
      bodies: [
        { title: "Problema que resolve", text: `Mostre a situação chata do dia a dia e, em seguida, ${p} resolvendo em poucos segundos.` },
        { title: "Demonstração", text: `Use ${p} na frente da câmera, do começo ao fim, sem cortes. Fale o que está sentindo.` },
        { title: "Comparação", text: `Coloque lado a lado com o jeito antigo de fazer e mostre a diferença.` },
        { title: "Detalhe de qualidade", text: `Câmera bem perto: acabamento, material, embalagem. Mostre o que dá confiança.` },
        { title: "Rotina de uso", text: `Mostre ${p} encaixado na sua rotina real: manhã, trabalho, noite.` },
      ],
      ctas: [
        { text: "Toca no carrinho laranja e garante o seu antes que acabe." },
        { text: "O link tá aqui embaixo, com desconto só hoje." },
        { text: "Corre no carrinho, que da última vez esgotou rapidinho." },
      ],
      recordingTips: [
        "Grave na vertical, com a luz de frente para você.",
        "Comece a falar no primeiro segundo: sem pausa no início.",
        "Grave cada gancho, corpo e CTA como um vídeo separado.",
      ],
    };
  }
  const stages = ["abertura", "dor", "desejo", "detalhe", "prova", "oferta", "cta", "interacao"] as const;
  const falas: Record<(typeof stages)[number], string> = {
    abertura: `Boa noite, gente! Quem chegou agora, comenta "cheguei" que hoje tem condição especial em ${p}.`,
    dor: "Sabe aquele problema que te irrita todo santo dia? Comenta aqui se você também passa por isso.",
    desejo: `Agora imagina resolver isso em segundos, sem complicação. É exatamente isso que ${p} faz.`,
    detalhe: "Olha de pertinho: o material, o acabamento, o tamanho. Vou mostrar funcionando agora.",
    prova: "Olha quantas pessoas já compraram e as avaliações. Vou ler algumas pra vocês.",
    oferta: "Só durante a live o preço tá esse aqui. Quando eu encerrar, volta ao normal.",
    cta: "Toca no carrinho laranja agora. Quem comprar, comenta 'comprei' que eu confirmo!",
    interacao: "Me conta aqui no chat: de qual cidade você tá assistindo?",
  };
  return {
    title: `Live: ${p}`,
    blocks: Array.from({ length: Math.ceil(input.liveMinutes / 8) }, (_, i) => {
      const stage = stages[i % stages.length]!;
      return { minute: i * 8, stage, title: `Bloco ${i + 1}`, text: falas[stage] };
    }),
    objections: [
      { question: "Chega rápido?", answer: "Fale o prazo real informado pela loja para a sua região." },
      { question: "Tem garantia?", answer: "Explique a garantia e a política de troca do TikTok Shop." },
      { question: "Serve pra mim?", answer: "Pergunte o caso da pessoa e mostre o produto nessa situação." },
    ],
    checklist: ["Produto carregado e testado", "Luz de frente e celular na vertical", "Cupom ou oferta da live configurados"],
  };
}

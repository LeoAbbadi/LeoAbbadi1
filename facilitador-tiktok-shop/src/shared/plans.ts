// Planos e limites. Usado pelo site (página de planos) e pelo servidor (cobrança de cota).
// Os valores foram calculados em docs/CUSTOS.md: mude aqui e o site inteiro acompanha.

export type PlanId = "free" | "starter" | "pro";
export type BillingPeriod = "monthly" | "annual";

export interface Plan {
  id: PlanId;
  name: string;
  tagline: string;
  /** preço em centavos de real */
  monthlyCents: number | null;
  annualCents: number | null;
  /** vídeos que o Multiplicador pode gerar por mês */
  videosPerMonth: number;
  /** máximo de vídeos em um único lote */
  maxVideosPerBatch: number;
  /** roteiros com IA por mês (vídeo ou live) */
  scriptsPerMonth: number;
  /** países liberados na pesquisa de produtos */
  countries: ("BR" | "US")[];
  features: string[];
}

export const PLANS: Record<PlanId, Plan> = {
  free: {
    id: "free",
    name: "Teste grátis",
    tagline: "Pra conhecer a ferramenta",
    monthlyCents: 0,
    annualCents: null,
    videosPerMonth: 20,
    maxVideosPerBatch: 20,
    scriptsPerMonth: 2,
    countries: ["BR"],
    features: [
      "Multiplicador: até 20 vídeos por mês",
      "2 roteiros com IA",
      "Top 10 produtos do Brasil",
    ],
  },
  starter: {
    id: "starter",
    name: "Criador",
    tagline: "Pra quem posta todo dia",
    monthlyCents: 4900,
    annualCents: null,
    videosPerMonth: 300,
    maxVideosPerBatch: 150,
    scriptsPerMonth: 15,
    countries: ["BR"],
    features: [
      "Multiplicador: até 300 vídeos por mês",
      "Ordem de postagem com selo de originalidade",
      "Calendário de postagem e legendas prontas",
      "15 roteiros com IA por mês (vídeo ou live)",
      "Ranking completo de produtos do Brasil",
    ],
  },
  pro: {
    id: "pro",
    name: "Pro",
    tagline: "Pra quem vive de TikTok Shop",
    monthlyCents: 8900,
    annualCents: 59700,
    videosPerMonth: 1500,
    maxVideosPerBatch: 250,
    scriptsPerMonth: 40,
    countries: ["BR", "US"],
    features: [
      "Multiplicador: até 1.500 vídeos por mês",
      "Lotes de até 250 vídeos",
      "40 roteiros com IA por mês (vídeo ou live)",
      "Produtos do Brasil e dos EUA",
      "Tendências 24h e vídeos que mais venderam",
    ],
  },
};

/** Limites de envio de pedaços por slot do Multiplicador */
export const SLOT_LIMITS = { hook: 10, body: 10, cta: 5 } as const;
export const MAX_CLIP_BYTES = 300 * 1024 * 1024;

export function formatBRL(cents: number): string {
  return (cents / 100).toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}

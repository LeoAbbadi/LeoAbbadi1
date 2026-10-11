// Calculadora de custo por cliente e margem de cada plano.
// Rode com: npm run custos
// Troque os números abaixo quando os preços dos fornecedores mudarem.
import { PLANS } from "../src/shared/plans.ts";

const DOLAR = 5.5; // R$ por US$ (ajuste para a cotação do dia)

// ---------- vídeo (medido neste projeto: 18 pedaços → 150 vídeos) ----------
// Padronizar 18 pedaços ~185 s de CPU + juntar 150 vídeos ~58 s + ZIP ~20 s ≈ 300 s de CPU por 150 vídeos.
const CPU_SEGUNDOS_POR_VIDEO = 300 / 150;
const VCPU_HORA_USD = 0.0278; // Railway: US$ 20 por vCPU/mês
const MB_POR_VIDEO = 20; // vídeo de ~23 s em 1080x1920
const DIAS_GUARDADO = 7; // OUTPUT_RETENTION_DAYS
const R2_GB_MES_USD = 0.015; // Cloudflare R2: armazenamento; download (egress) é grátis
const R2_ESCRITA_USD = 4.5 / 1_000_000;
const ESCRITAS_POR_VIDEO = 2; // o vídeo + sua parte do ZIP
const PEDACOS_GB_POR_PROJETO = 0.7; // originais + padronizados, guardados enquanto o projeto existe

// ---------- IA (Claude) ----------
const MODELOS = {
  "claude-opus-5-5": { entrada: 4.0, saida: 20.0 }, // US$ por milhão de tokens
  "claude-haiku-5-5": { entrada: 0.1, saida: 0.5 },
};
// tokens estimados por roteiro (saída inclui o raciocínio do modelo)
const ROTEIRO_VIDEO = { entrada: 700, saida: 3500 };
const ROTEIRO_LIVE = { entrada: 800, saida: 8000 };
const FRACAO_LIVES = 0.3;

// ---------- pagamento (Stripe Brasil, cartão nacional; confira a tabela atual) ----------
const TAXA_PCT = 0.0399;
const TAXA_FIXA = 0.39;

function custoVideoUSD(): number {
  const cpu = (CPU_SEGUNDOS_POR_VIDEO / 3600) * VCPU_HORA_USD;
  const armazenamento = ((MB_POR_VIDEO * 2) / 1024) * R2_GB_MES_USD * (DIAS_GUARDADO / 30);
  const escritas = ESCRITAS_POR_VIDEO * R2_ESCRITA_USD;
  return cpu + armazenamento + escritas;
}

function custoRoteiroUSD(modelo: keyof typeof MODELOS): number {
  const p = MODELOS[modelo];
  const c = (t: { entrada: number; saida: number }) => (t.entrada * p.entrada + t.saida * p.saida) / 1_000_000;
  return (1 - FRACAO_LIVES) * c(ROTEIRO_VIDEO) + FRACAO_LIVES * c(ROTEIRO_LIVE);
}

const brl = (v: number) => `R$ ${v.toFixed(2).replace(".", ",")}`;
const pct = (v: number) => `${Math.round(v * 100)}%`;

console.log(`\nCusto por vídeo gerado: US$ ${custoVideoUSD().toFixed(5)} (R$ ${(custoVideoUSD() * DOLAR).toFixed(4).replace(".", ",")}; 150 vídeos = ${brl(150 * custoVideoUSD() * DOLAR)})`);
for (const m of Object.keys(MODELOS) as (keyof typeof MODELOS)[]) {
  console.log(`Custo por roteiro com ${m}: US$ ${custoRoteiroUSD(m).toFixed(4)} (${brl(custoRoteiroUSD(m) * DOLAR)})`);
}

for (const uso of [1, 0.35]) {
  console.log(`\n=== Cliente usando ${pct(uso)} da cota ===`);
  console.log("plano            | receita/mês | vídeos+arquivos |  IA (Opus) | IA (Haiku) | taxa pgto | margem Opus | margem Haiku");
  const linhas: [string, number, number][] = [];
  for (const plan of Object.values(PLANS)) {
    if (plan.monthlyCents) linhas.push([`${plan.name} mensal`, plan.monthlyCents / 100, 1]);
    if (plan.annualCents) linhas.push([`${plan.name} anual`, plan.annualCents / 100 / 12, 12]);
    if (plan.monthlyCents === 0) linhas.push([plan.name, 0, 1]);
  }
  for (const [nome, receita, meses] of linhas) {
    const plan = Object.values(PLANS).find((p) => nome.startsWith(p.name))!;
    const videos = plan.videosPerMonth * uso;
    const roteiros = plan.scriptsPerMonth * uso;
    const arquivos = (videos * custoVideoUSD() + PEDACOS_GB_POR_PROJETO * R2_GB_MES_USD) * DOLAR;
    const iaOpus = roteiros * custoRoteiroUSD("claude-opus-5-5") * DOLAR;
    const iaHaiku = roteiros * custoRoteiroUSD("claude-haiku-5-5") * DOLAR;
    const taxa = receita > 0 ? (receita * meses * TAXA_PCT + TAXA_FIXA) / meses : 0;
    const m = (ia: number) => (receita > 0 ? `${brl(receita - arquivos - ia - taxa)} (${pct((receita - arquivos - ia - taxa) / receita)})` : brl(-arquivos - ia));
    console.log(
      `${nome.padEnd(16)} | ${brl(receita).padStart(11)} | ${brl(arquivos).padStart(15)} | ${brl(iaOpus).padStart(10)} | ${brl(iaHaiku).padStart(10)} | ${brl(taxa).padStart(9)} | ${m(iaOpus).padStart(11)} | ${m(iaHaiku)}`,
    );
  }
}

// custos fixos mensais
const FIXOS = [
  ["Railway (site + worker + banco)", 30 * DOLAR],
  ["Cloudflare R2 (base)", 5 * DOLAR],
  ["Domínio (R$ 40/ano)", 40 / 12],
] as const;
const fixos = FIXOS.reduce((s, [, v]) => s + v, 0);
console.log(`\nCustos fixos mensais sem provedor de dados: ${brl(fixos)}`);
for (const [k, v] of FIXOS) console.log(`  - ${k}: ${brl(v)}`);
console.log("  + provedor de dados do TikTok Shop: peça orçamento (veja docs/DADOS.md)\n");

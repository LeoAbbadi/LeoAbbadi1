// Roteiros com IA (Claude).
// - "videos": 10 ganchos, 5 corpos e 3 CTAs, já no formato do Multiplicador.
// - "live": roteiro de live em blocos (Dor → Desejo → Detalhe → CTA) para teleprompter.
// Sem ANTHROPIC_API_KEY, devolve um roteiro de exemplo para o site funcionar em desenvolvimento.
import Anthropic from "@anthropic-ai/sdk";
import { betaZodOutputFormat } from "@anthropic-ai/sdk/helpers/beta/zod";
import { z } from "zod";
import { config } from "./config.ts";
import { sampleScript } from "../shared/samples.ts";

export const scriptInput = z.object({
  kind: z.enum(["videos", "live"]),
  productName: z.string().trim().min(2, "Digite o nome do produto.").max(200),
  details: z.string().trim().max(2000).default(""),
  audience: z.string().trim().max(200).default(""),
  tone: z.enum(["animado", "direto", "engracado", "confiavel"]).default("animado"),
  liveMinutes: z.number().int().min(15).max(240).default(120),
});
export type ScriptInput = z.infer<typeof scriptInput>;

const VideoScript = z.object({
  hooks: z.array(z.object({ text: z.string(), technique: z.string() })),
  bodies: z.array(z.object({ title: z.string(), text: z.string() })),
  ctas: z.array(z.object({ text: z.string() })),
  recordingTips: z.array(z.string()),
});

const LiveScript = z.object({
  title: z.string(),
  blocks: z.array(
    z.object({
      minute: z.number().int(),
      stage: z.enum(["abertura", "dor", "desejo", "detalhe", "prova", "oferta", "cta", "interacao"]),
      title: z.string(),
      text: z.string(),
    }),
  ),
  objections: z.array(z.object({ question: z.string(), answer: z.string() })),
  checklist: z.array(z.string()),
});

export type VideoScriptOutput = z.infer<typeof VideoScript>;
export type LiveScriptOutput = z.infer<typeof LiveScript>;

export interface ScriptResult {
  output: VideoScriptOutput | LiveScriptOutput;
  model: string;
  inputTokens: number;
  outputTokens: number;
}

const TONE: Record<ScriptInput["tone"], string> = {
  animado: "animado e com energia",
  direto: "direto e objetivo",
  engracado: "bem-humorado",
  confiavel: "calmo e confiável, como quem indica para um amigo",
};

const SYSTEM = `Você escreve roteiros para criadores de conteúdo que vendem no TikTok Shop Brasil.
Escreva em português do Brasil falado, frases curtas, fáceis de gravar no celular.
Não invente números, prêmios, certificações ou resultados que não foram informados sobre o produto.
Não faça promessas de saúde, cura ou ganho financeiro garantido. Siga as regras de conteúdo do TikTok Shop.`;

function videoPrompt(i: ScriptInput): string {
  return `Produto: ${i.productName}
${i.details ? `Informações do produto: ${i.details}\n` : ""}${i.audience ? `Público: ${i.audience}\n` : ""}Tom: ${TONE[i.tone]}

Crie o material para o Multiplicador de vídeos. O criador grava cada pedaço separado e a ferramenta junta tudo em combinações gancho + corpo + CTA, então cada corpo precisa funcionar depois de qualquer gancho, e cada CTA depois de qualquer corpo.

- hooks: exatamente 10 ganchos de 2 a 4 segundos, cada um com uma técnica diferente (curiosidade, dor, polêmica leve, prova visual, pergunta, lista, antes e depois, segredo, urgência, identificação). Em "technique", diga a técnica em poucas palavras.
- bodies: exatamente 5 corpos de 15 a 25 segundos. Cada um mostra o produto por um ângulo diferente (problema que resolve, demonstração, comparação, detalhe de qualidade, rotina de uso). Em "title" um nome curto do ângulo.
- ctas: exatamente 3 chamadas finais de 3 a 5 segundos levando ao carrinho laranja.
- recordingTips: 3 a 5 dicas práticas de gravação para este produto.`;
}

function livePrompt(i: ScriptInput): string {
  return `Produto: ${i.productName}
${i.details ? `Informações do produto: ${i.details}\n` : ""}${i.audience ? `Público: ${i.audience}\n` : ""}Tom: ${TONE[i.tone]}
Duração da live: ${i.liveMinutes} minutos

Monte o roteiro da live em blocos com o minuto de início de cada um, cobrindo a duração inteira. Use o ciclo Dor → Desejo → Detalhe → CTA e repita o ciclo ao longo da live, porque o público entra e sai o tempo todo. Inclua blocos de interação com o chat a cada 10 a 15 minutos. Em "text", escreva a fala para ler no teleprompter.
Em "objections", liste as 5 a 8 dúvidas mais prováveis do chat com a resposta.
Em "checklist", o que preparar antes de entrar ao vivo.`;
}

let client: Anthropic | null = null;

export async function generateScript(input: ScriptInput): Promise<ScriptResult> {
  if (!config.anthropicApiKey) return demoScript(input);
  client ??= new Anthropic({ apiKey: config.anthropicApiKey });

  const isLive = input.kind === "live";
  const params = {
    model: config.anthropicModel,
    max_tokens: isLive ? 32000 : 16000,
    system: SYSTEM,
    output_config: {
      effort: "medium" as const,
      format: isLive ? betaZodOutputFormat(LiveScript) : betaZodOutputFormat(VideoScript),
    },
    messages: [{ role: "user" as const, content: isLive ? livePrompt(input) : videoPrompt(input) }],
  };

  // A recusa por segurança é rara aqui, mas os modelos Opus/Sonnet aceitam fallback automático no servidor.
  const supportsFallback = /^claude-(opus|sonnet|fable)/.test(config.anthropicModel);
  const stream = client.beta.messages.stream({
    ...params,
    ...(supportsFallback ? { betas: ["server-side-fallback-2026-07-01"], fallbacks: "default" as const } : {}),
  });
  const message = await stream.finalMessage();

  if (message.stop_reason === "refusal") {
    throw new Error("A IA não conseguiu escrever esse roteiro. Revise as informações do produto e tente de novo.");
  }
  if (message.stop_reason === "max_tokens") {
    throw new Error("O roteiro ficou longo demais. Tente uma live mais curta.");
  }
  const text = message.content.flatMap((b) => (b.type === "text" ? [b.text] : [])).join("");
  const output = (isLive ? LiveScript : VideoScript).parse(JSON.parse(text));
  return {
    output,
    model: message.model,
    inputTokens: message.usage.input_tokens,
    outputTokens: message.usage.output_tokens,
  };
}

function demoScript(input: ScriptInput): ScriptResult {
  return { output: sampleScript(input), model: "exemplo-sem-ia", inputTokens: 0, outputTokens: 0 };
}

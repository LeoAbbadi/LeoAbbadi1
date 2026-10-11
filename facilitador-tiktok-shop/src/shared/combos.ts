// Monta as combinações gancho × corpo × CTA e decide a ordem de postagem.
//
// A ordem é escolhida de forma gulosa: a cada passo pega a combinação que menos
// repete o que já foi postado. Isso faz os ganchos novos saírem primeiro, evita
// o mesmo corpo em dois posts seguidos e, quando o usuário pede menos vídeos
// do que o total possível, entrega os mais diferentes entre si.

export type OriginalityLabel = "original" | "variacao" | "parecido";

export interface Combo {
  hook: string;
  body: string;
  cta: string;
}

export interface PlannedVideo extends Combo {
  position: number;
  label: OriginalityLabel;
  /** 0 a 100: quanto este vídeo difere de tudo que foi postado antes dele */
  originality: number;
  /** dias a partir da data inicial (0 = primeiro dia) */
  dayOffset: number;
}

export function totalCombinations(hooks: number, bodies: number, ctas: number): number {
  return hooks * bodies * ctas;
}

export function planVideos(
  hooks: string[],
  bodies: string[],
  ctas: string[],
  count: number,
  postsPerDay = 1,
): PlannedVideo[] {
  const total = totalCombinations(hooks.length, bodies.length, ctas.length);
  const n = Math.max(0, Math.min(count, total));
  if (n === 0) return [];

  const candidates: Combo[] = [];
  for (const hook of hooks) for (const body of bodies) for (const cta of ctas) candidates.push({ hook, body, cta });
  const used = new Array<boolean>(candidates.length).fill(false);

  const hookUses = new Map<string, number>();
  const bodyUses = new Map<string, number>();
  const ctaUses = new Map<string, number>();
  const pairUses = new Map<string, number>();
  const get = (m: Map<string, number>, k: string) => m.get(k) ?? 0;
  const pairKey = (c: Combo) => `${c.hook}|${c.body}`;

  const result: PlannedVideo[] = [];
  let prev: Combo | null = null;

  for (let position = 0; position < n; position++) {
    let best = -1;
    let bestPenalty = Infinity;
    for (let i = 0; i < candidates.length; i++) {
      if (used[i]) continue;
      const c = candidates[i]!;
      // O gancho pesa mais: é o que a pessoa vê nos primeiros segundos.
      let penalty =
        1000 * get(hookUses, c.hook) +
        100 * get(pairUses, pairKey(c)) +
        10 * get(bodyUses, c.body) +
        1 * get(ctaUses, c.cta);
      if (prev) {
        if (prev.body === c.body) penalty += 50;
        if (prev.cta === c.cta) penalty += 5;
      }
      if (penalty < bestPenalty) {
        bestPenalty = penalty;
        best = i;
      }
    }
    used[best] = true;
    const c = candidates[best]!;

    const hookRepeated = get(hookUses, c.hook) > 0;
    const pairRepeated = get(pairUses, pairKey(c)) > 0;
    const bodyRepeated = get(bodyUses, c.body) > 0;
    const ctaRepeated = get(ctaUses, c.cta) > 0;
    const label: OriginalityLabel = !hookRepeated ? "original" : !pairRepeated ? "variacao" : "parecido";
    const originality = Math.max(
      0,
      100 - (hookRepeated ? 40 : 0) - (pairRepeated ? 30 : 0) - (bodyRepeated ? 15 : 0) - (ctaRepeated ? 10 : 0),
    );

    result.push({ ...c, position, label, originality, dayOffset: Math.floor(position / Math.max(1, postsPerDay)) });

    hookUses.set(c.hook, get(hookUses, c.hook) + 1);
    bodyUses.set(c.body, get(bodyUses, c.body) + 1);
    ctaUses.set(c.cta, get(ctaUses, c.cta) + 1);
    pairUses.set(pairKey(c), get(pairUses, pairKey(c)) + 1);
    prev = c;
  }
  return result;
}

export const LABEL_INFO: Record<OriginalityLabel, { title: string; tip: string }> = {
  original: { title: "Original", tip: "Gancho inédito. Poste primeiro, à vontade." },
  variacao: {
    title: "Variação",
    tip: "Gancho já usado com outro corpo. Mude a legenda e o texto na tela.",
  },
  parecido: {
    title: "Parecido",
    tip: "Só o CTA muda. Deixe por último e espace dos parecidos.",
  },
};

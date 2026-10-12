// Fila de montagem da demonstração: um vídeo por vez (gravar dois ao mesmo tempo
// pesaria no celular). Guarda os vídeos já montados para baixar de novo sem refazer.
import { useSyncExternalStore } from "react";
import { renderSequence, saveFile, type RenderResult } from "./render.ts";

export type JobState =
  | { status: "idle" }
  | { status: "queued" }
  | { status: "rendering"; progress: number }
  | { status: "ready"; result: RenderResult }
  | { status: "error"; message: string };

const states = new Map<string, JobState>();
const listeners = new Set<() => void>();
let version = 0;
let chain: Promise<unknown> = Promise.resolve();

function set(id: string, s: JobState) {
  states.set(id, s);
  version++;
  listeners.forEach((l) => l());
}

export function useJob(id: string): JobState {
  useSyncExternalStore(
    (l) => {
      listeners.add(l);
      return () => listeners.delete(l);
    },
    () => version,
  );
  return states.get(id) ?? { status: "idle" };
}

/** Monta (se ainda não montou) e devolve o vídeo final. */
export function render(id: string, urls: string[]): Promise<RenderResult> {
  const cur = states.get(id);
  if (cur?.status === "ready") return Promise.resolve(cur.result);
  set(id, { status: "queued" });
  const job = chain.then(async () => {
    set(id, { status: "rendering", progress: 0 });
    try {
      const result = await renderSequence(urls, (progress) => set(id, { status: "rendering", progress }));
      set(id, { status: "ready", result });
      return result;
    } catch (err) {
      set(id, { status: "error", message: (err as Error).message });
      throw err;
    }
  });
  chain = job.catch(() => undefined);
  return job;
}

export function fileName(position: number, ext: string): string {
  return `video-${String(position + 1).padStart(3, "0")}.${ext}`;
}

export async function renderAndSave(id: string, position: number, urls: string[]): Promise<void> {
  const result = await render(id, urls);
  await saveFile(fileName(position, result.ext), result.blob);
}

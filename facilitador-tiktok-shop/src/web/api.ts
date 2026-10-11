import type { PlanId } from "../shared/plans.ts";
import type { OriginalityLabel } from "../shared/combos.ts";

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

export async function api<T>(path: string, init: { method?: string; body?: unknown } = {}): Promise<T> {
  const res = await fetch(path, {
    method: init.method ?? (init.body === undefined ? "GET" : "POST"),
    headers: init.body === undefined ? undefined : { "content-type": "application/json" },
    body: init.body === undefined ? undefined : JSON.stringify(init.body),
    credentials: "same-origin",
  });
  const data = (await res.json().catch(() => ({}))) as { error?: string };
  if (!res.ok) throw new ApiError(res.status, data.error ?? "Algo deu errado. Tente de novo.");
  return data as T;
}

/** Envia o arquivo direto para o armazenamento, com progresso. */
export function uploadFile(url: string, file: File, onProgress: (pct: number) => void): Promise<void> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("PUT", url);
    xhr.setRequestHeader("content-type", file.type || "video/mp4");
    xhr.upload.onprogress = (e) => e.lengthComputable && onProgress(Math.round((e.loaded / e.total) * 100));
    xhr.onload = () => (xhr.status < 300 ? resolve() : reject(new Error("Falha no envio. Tente de novo.")));
    xhr.onerror = () => reject(new Error("Falha no envio. Confira sua internet."));
    xhr.send(file);
  });
}

export interface Me {
  user: {
    id: string;
    email: string;
    name: string;
    isAdmin: boolean;
    plan: PlanId;
    planPeriod: "monthly" | "annual" | null;
    planStatus: string;
    planRenewsAt: string | null;
    hasBilling: boolean;
  };
  limits: { videosPerMonth: number; maxVideosPerBatch: number; scriptsPerMonth: number; countries: ("BR" | "US")[] };
  usage: { videos: number; scripts: number };
}

export type Slot = "hook" | "body" | "cta";

export interface Clip {
  id: string;
  slot: Slot;
  label: string;
  name: string;
  sizeBytes: number;
  durationS: number | null;
  previewUrl: string;
}

export interface BatchSummary {
  id: string;
  status: "queued" | "processing" | "done" | "error" | "expired";
  total: number;
  done: number;
  error: string | null;
  zipSizeBytes: number | null;
  postsPerDay: number;
  startDate: string;
  createdAt: string;
  finishedAt: string | null;
  expiresAt: string | null;
}

export interface ProjectSummary {
  id: string;
  name: string;
  product_name: string;
  created_at: string;
  clips: number;
  videos: number;
}

export interface ProjectDetail {
  project: { id: string; name: string; product_name: string; created_at: string };
  clips: Clip[];
  batches: BatchSummary[];
}

export interface Output {
  id: string;
  position: number;
  label: OriginalityLabel;
  originality: number;
  suggestedDate: string;
  caption: string;
  parts: { hook: string; body: string; cta: string; hookText: string };
  sizeBytes: number | null;
  durationS: number | null;
  url: string | null;
  downloadUrl: string | null;
}

export interface BatchDetail {
  batch: BatchSummary & { projectId: string; projectName: string; zipUrl: string | null };
  outputs: Output[];
}

export interface Product {
  id: string;
  name: string;
  category: string;
  shop_name: string;
  image_url: string;
  product_url: string;
  price_cents: number;
  commission_pct: number;
  sales: number;
  gmv_cents: string | number;
  growth_pct_1d: number;
  creators_count: number;
  is_sample: boolean;
  updated_at: string;
  favorite: boolean;
}

export interface ScriptSummary {
  id: string;
  kind: "videos" | "live";
  product_name: string;
  created_at: string;
}

export interface VideoScript {
  hooks: { text: string; technique: string }[];
  bodies: { title: string; text: string }[];
  ctas: { text: string }[];
  recordingTips: string[];
}

export interface LiveScript {
  title: string;
  blocks: { minute: number; stage: string; title: string; text: string }[];
  objections: { question: string; answer: string }[];
  checklist: string[];
}

export interface ScriptDetail extends ScriptSummary {
  input: { productName: string; details: string; audience: string; tone: string; liveMinutes: number };
  output: VideoScript | LiveScript;
}

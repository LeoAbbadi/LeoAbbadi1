// Modo demonstração: imita a API inteira dentro do navegador, sem servidor.
// Usado na versão publicada como prévia (build com VITE_DEMO=1).
// - Login: qualquer e-mail e senha funcionam.
// - Vídeos enviados ficam só na memória desta aba (URL blob:) e somem ao recarregar.
// - "Gerar vídeos" simula o worker; cada vídeo é tocado em sequência (gancho → corpo → CTA).
import { planVideos, type OriginalityLabel } from "../../shared/combos.ts";
import { PLANS, SLOT_LIMITS, type PlanId } from "../../shared/plans.ts";
import { sampleProducts, sampleScript } from "../../shared/samples.ts";

type Slot = "hook" | "body" | "cta";

class DemoError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

interface User {
  id: string;
  email: string;
  name: string;
  plan: PlanId;
  planPeriod: "monthly" | "annual" | null;
  renews: string | null;
}
interface Clip {
  id: string;
  projectId: string;
  slot: Slot;
  label: string;
  name: string;
  size: number;
  url: string | null;
}
interface Project {
  id: string;
  name: string;
  productName: string;
  createdAt: string;
}
interface Output {
  id: string;
  position: number;
  hook: string;
  body: string;
  cta: string;
  label: OriginalityLabel;
  originality: number;
  date: string;
  caption: string;
}
interface Batch {
  id: string;
  projectId: string;
  total: number;
  postsPerDay: number;
  startDate: string;
  createdAt: number;
  outputs: Output[];
}

const uid = () => crypto.randomUUID();
const now = () => new Date().toISOString();

function createDb() {
  const db = {
  user: null as User | null,
  usage: { videos: 0, scripts: 0 },
  projects: [] as Project[],
  clips: [] as Clip[],
  batches: [] as Batch[],
  scripts: [] as { id: string; kind: "videos" | "live"; product_name: string; created_at: string; input: unknown; output: unknown }[],
  favorites: new Set<string>(),
  products: sampleProducts().map((p, i) => ({
    ...p,
    id: `p${i}`,
    image_url: "",
    product_url: "",
    is_sample: true,
    updated_at: now(),
  })),
  };
  // login lembrado entre recarregamentos (só os dados da conta)
  try {
    const saved = localStorage.getItem("demo-user");
    if (saved) db.user = JSON.parse(saved) as User;
  } catch {
    /* sem armazenamento: começa deslogado */
  }
  return db;
}

let state: ReturnType<typeof createDb> | null = null;
const getDb = () => (state ??= createDb());
function saveUser() {
  const db = getDb();
  try {
    if (db.user) localStorage.setItem("demo-user", JSON.stringify(db.user));
    else localStorage.removeItem("demo-user");
  } catch {
    /* ignora */
  }
}

function me() {
  const db = getDb();
  const u = db.user!;
  const plan = PLANS[u.plan];
  return {
    user: {
      id: u.id,
      email: u.email,
      name: u.name,
      isAdmin: false,
      plan: u.plan,
      planPeriod: u.planPeriod,
      planStatus: "active",
      planRenewsAt: u.renews,
      hasBilling: false,
    },
    limits: {
      videosPerMonth: plan.videosPerMonth,
      maxVideosPerBatch: plan.maxVideosPerBatch,
      scriptsPerMonth: plan.scriptsPerMonth,
      countries: plan.countries,
    },
    usage: db.usage,
  };
}

function requireUser(): User {
  const db = getDb();
  if (!db.user) throw new DemoError(401, "Faça login para continuar.");
  return db.user;
}

const VIDEO_MS = 60; // velocidade da simulação: ~9 s para 150 vídeos

function batchState(b: Batch) {
  const elapsed = Date.now() - b.createdAt;
  if (elapsed < 1200) return { status: "queued" as const, done: 0 };
  const done = Math.min(b.total, Math.floor((elapsed - 2200) / VIDEO_MS));
  if (done >= b.total) return { status: "done" as const, done: b.total };
  return { status: "processing" as const, done: Math.max(0, done) };
}

function batchSummary(b: Batch) {
  const st = batchState(b);
  return {
    id: b.id,
    status: st.status,
    total: b.total,
    done: st.done,
    error: null,
    zipSizeBytes: null,
    postsPerDay: b.postsPerDay,
    startDate: b.startDate,
    createdAt: new Date(b.createdAt).toISOString(),
    finishedAt: st.status === "done" ? now() : null,
    expiresAt: new Date(b.createdAt + 7 * 86400_000).toISOString(),
  };
}

function caption(productName: string, hookText: string): string {
  const tag = productName
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .toLowerCase()
    .split(/\s+/)
    .slice(0, 3)
    .join("")
    .replace(/[^a-z0-9]/g, "");
  return [hookText.trim(), [tag && `#${tag}`, "#tiktokshop", "#achadinhos"].filter(Boolean).join(" ")].filter(Boolean).join("\n\n");
}

function addDays(iso: string, days: number): string {
  const d = new Date(`${iso}T12:00:00`);
  d.setDate(d.getDate() + days);
  return d.toISOString().slice(0, 10);
}

// ---------- uploads ----------

export async function demoUpload(url: string, file: File, onProgress: (pct: number) => void): Promise<void> {
  const db = getDb();
  const clip = db.clips.find((c) => `demo:${c.id}` === url);
  if (!clip) throw new Error("Envio inválido.");
  for (const pct of [25, 60, 100]) {
    await new Promise((r) => setTimeout(r, 90));
    onProgress(pct);
  }
  clip.url = URL.createObjectURL(file);
}

// ---------- rotas ----------

type Body = Record<string, unknown>;

export async function demoApi<T>(path: string, init: { method?: string; body?: unknown } = {}): Promise<T> {
  const db = getDb();
  await new Promise((r) => setTimeout(r, 60)); // parece rede de verdade
  const method = init.method ?? (init.body === undefined ? "GET" : "POST");
  const url = new URL(path, "http://demo");
  const p = url.pathname;
  const q = url.searchParams;
  const body = (init.body ?? {}) as Body;
  const m = (re: RegExp) => p.match(re);
  let r: RegExpMatchArray | null;

  // conta
  if (p === "/api/me") return (db.user ? me() : { user: null }) as T;
  if (p === "/api/auth/login" || p === "/api/auth/signup") {
    const email = String(body.email ?? "").trim().toLowerCase();
    if (!email.includes("@")) throw new DemoError(400, "Digite um e-mail válido.");
    if (p.endsWith("signup") && String(body.password ?? "").length < 8) throw new DemoError(400, "A senha precisa de pelo menos 8 caracteres.");
    db.user = {
      id: uid(),
      email,
      name: String(body.name ?? "") || email.split("@")[0]!,
      plan: "free",
      planPeriod: null,
      renews: null,
    };
    saveUser();
    return { ok: true } as T;
  }
  if (p === "/api/auth/logout") {
    db.user = null;
    saveUser();
    return { ok: true } as T;
  }

  const user = requireUser();
  const plan = PLANS[user.plan];

  // pagamento (demonstração: ativa o plano na hora)
  if (p === "/api/billing/checkout") {
    const period = body.period as "monthly" | "annual";
    const renews = new Date();
    renews.setMonth(renews.getMonth() + (period === "annual" ? 12 : 1));
    user.plan = body.plan as PlanId;
    user.planPeriod = period;
    user.renews = renews.toISOString();
    saveUser();
    return { url: "app:/app/conta?assinatura=ok" } as T;
  }
  if (p === "/api/billing/portal") throw new DemoError(400, "O portal de pagamentos funciona no site publicado.");

  // projetos
  if (p === "/api/projects" && method === "GET") {
    return db.projects.map((pr) => ({
      id: pr.id,
      name: pr.name,
      product_name: pr.productName,
      created_at: pr.createdAt,
      clips: db.clips.filter((c) => c.projectId === pr.id && c.url).length,
      videos: db.batches.filter((b) => b.projectId === pr.id && batchState(b).status === "done").reduce((s, b) => s + b.total, 0),
    })) as T;
  }
  if (p === "/api/projects" && method === "POST") {
    const name = String(body.name ?? "").trim();
    if (!name) throw new DemoError(400, "Dê um nome ao projeto.");
    const pr = { id: uid(), name, productName: String(body.productName ?? ""), createdAt: now() };
    db.projects.unshift(pr);
    return { id: pr.id, name: pr.name, product_name: pr.productName } as T;
  }
  if ((r = m(/^\/api\/projects\/([^/]+)$/))) {
    const pr = db.projects.find((x) => x.id === r![1]);
    if (!pr) throw new DemoError(404, "Projeto não encontrado.");
    if (method === "DELETE") {
      db.projects = db.projects.filter((x) => x !== pr);
      db.clips = db.clips.filter((c) => c.projectId !== pr.id);
      db.batches = db.batches.filter((b) => b.projectId !== pr.id);
      return { ok: true } as T;
    }
    if (method === "PATCH") {
      if (body.name) pr.name = String(body.name);
      if (body.productName !== undefined) pr.productName = String(body.productName);
      return { ok: true } as T;
    }
    return {
      project: { id: pr.id, name: pr.name, product_name: pr.productName, created_at: pr.createdAt },
      clips: db.clips
        .filter((c) => c.projectId === pr.id && c.url)
        .map((c) => ({ id: c.id, slot: c.slot, label: c.label, name: c.name, sizeBytes: c.size, durationS: null, previewUrl: c.url! })),
      batches: db.batches.filter((b) => b.projectId === pr.id).map(batchSummary),
    } as T;
  }

  // pedaços
  if ((r = m(/^\/api\/projects\/([^/]+)\/clips$/))) {
    const slot = body.slot as Slot;
    const count = db.clips.filter((c) => c.projectId === r![1] && c.slot === slot && c.url).length;
    if (count >= SLOT_LIMITS[slot]) throw new DemoError(400, `Limite de ${SLOT_LIMITS[slot]} vídeos nesta caixa.`);
    const clip: Clip = { id: uid(), projectId: r[1]!, slot, label: "", name: String(body.filename), size: Number(body.size), url: null };
    db.clips.push(clip);
    return { clipId: clip.id, uploadUrl: `demo:${clip.id}` } as T;
  }
  if ((r = m(/^\/api\/clips\/([^/]+)\/complete$/))) return { ok: true } as T;
  if ((r = m(/^\/api\/clips\/([^/]+)$/))) {
    const clip = db.clips.find((c) => c.id === r![1]);
    if (!clip) throw new DemoError(404, "Vídeo não encontrado.");
    if (method === "PATCH") clip.label = String(body.label ?? "");
    if (method === "DELETE") db.clips = db.clips.filter((c) => c !== clip);
    return { ok: true } as T;
  }

  // lotes
  if ((r = m(/^\/api\/projects\/([^/]+)\/batches$/))) {
    const pr = db.projects.find((x) => x.id === r![1])!;
    const clips = db.clips.filter((c) => c.projectId === pr.id && c.url);
    const ids = (s: Slot) => clips.filter((c) => c.slot === s).map((c) => c.id);
    const hooks = ids("hook");
    const bodies = ids("body");
    const ctas = ids("cta");
    if (!hooks.length || !bodies.length || !ctas.length) throw new DemoError(400, "Envie pelo menos 1 gancho, 1 corpo e 1 CTA.");
    const count = Math.min(Number(body.count), hooks.length * bodies.length * ctas.length, plan.maxVideosPerBatch);
    if (db.usage.videos + count > plan.videosPerMonth) {
      throw new DemoError(402, `Seu plano não tem cota para ${count} vídeos este mês. Gere menos vídeos ou mude de plano.`);
    }
    db.usage.videos += count;
    const postsPerDay = Number(body.postsPerDay ?? 1);
    const startDate = String(body.startDate ?? now().slice(0, 10));
    const labels = new Map(clips.map((c) => [c.id, c.label]));
    const batch: Batch = {
      id: uid(),
      projectId: pr.id,
      total: count,
      postsPerDay,
      startDate,
      createdAt: Date.now(),
      outputs: planVideos(hooks, bodies, ctas, count, postsPerDay).map((v) => ({
        id: uid(),
        position: v.position,
        hook: v.hook,
        body: v.body,
        cta: v.cta,
        label: v.label,
        originality: v.originality,
        date: addDays(startDate, v.dayOffset),
        caption: caption(pr.productName, labels.get(v.hook) ?? ""),
      })),
    };
    db.batches.unshift(batch);
    return { batchId: batch.id, total: count } as T;
  }
  if ((r = m(/^\/api\/batches\/([^/]+)$/))) {
    const b = db.batches.find((x) => x.id === r![1]);
    if (!b) throw new DemoError(404, "Lote não encontrado.");
    const pr = db.projects.find((x) => x.id === b.projectId)!;
    const clip = (id: string) => db.clips.find((c) => c.id === id);
    const done = batchState(b).status === "done";
    return {
      batch: { ...batchSummary(b), projectId: pr.id, projectName: pr.name, zipUrl: null },
      outputs: b.outputs.map((o) => ({
        id: o.id,
        position: o.position,
        label: o.label,
        originality: o.originality,
        suggestedDate: o.date,
        caption: o.caption,
        parts: { hook: clip(o.hook)?.name ?? "", body: clip(o.body)?.name ?? "", cta: clip(o.cta)?.name ?? "", hookText: clip(o.hook)?.label ?? "" },
        sizeBytes: null,
        durationS: null,
        url: null,
        downloadUrl: null,
        sequence: done ? [clip(o.hook)?.url, clip(o.body)?.url, clip(o.cta)?.url].filter((u): u is string => !!u) : undefined,
      })),
    } as T;
  }
  if ((r = m(/^\/api\/outputs\/([^/]+)$/))) {
    for (const b of db.batches) {
      const o = b.outputs.find((x) => x.id === r![1]);
      if (o) o.caption = String(body.caption ?? "");
    }
    return { ok: true } as T;
  }

  // roteiros
  if (p === "/api/scripts" && method === "GET") {
    return db.scripts.map(({ id, kind, product_name, created_at }) => ({ id, kind, product_name, created_at })) as T;
  }
  if (p === "/api/scripts" && method === "POST") {
    if (db.usage.scripts + 1 > plan.scriptsPerMonth) throw new DemoError(402, "Você usou todos os roteiros do seu plano este mês.");
    const productName = String(body.productName ?? "").trim();
    if (productName.length < 2) throw new DemoError(400, "Digite o nome do produto.");
    await new Promise((res) => setTimeout(res, 1400));
    db.usage.scripts += 1;
    const input = { ...body, productName, liveMinutes: Number(body.liveMinutes ?? 120) };
    const kind = body.kind === "live" ? "live" : "videos";
    const s = {
      id: uid(),
      kind: kind as "videos" | "live",
      product_name: productName,
      created_at: now(),
      input,
      output: sampleScript({ kind, productName, liveMinutes: input.liveMinutes }),
    };
    db.scripts.unshift(s);
    return s as T;
  }
  if ((r = m(/^\/api\/scripts\/([^/]+)$/))) {
    const s = db.scripts.find((x) => x.id === r![1]);
    if (method === "DELETE") {
      db.scripts = db.scripts.filter((x) => x !== s);
      return { ok: true } as T;
    }
    if (!s) throw new DemoError(404, "Roteiro não encontrado.");
    return s as T;
  }

  // produtos
  if (p === "/api/products/categories") return [...new Set(db.products.map((x) => x.category))].sort() as T;
  if (p === "/api/products") {
    const country = (q.get("country") ?? "BR") as "BR" | "US";
    if (!plan.countries.includes(country)) throw new DemoError(402, "Os produtos dos EUA fazem parte do plano Pro.");
    const period = (q.get("period") ?? "7d") as "1d" | "7d" | "30d";
    const sort = q.get("sort") ?? "gmv";
    const cat = q.get("category");
    const term = q.get("q")?.toLowerCase();
    const limit = Number(q.get("limit") ?? 50);
    let items = db.products.filter(
      (x) => x.country === country && (!cat || x.category === cat) && (!term || `${x.name} ${x.shop_name}`.toLowerCase().includes(term)),
    );
    const key = (x: (typeof items)[number]) =>
      sort === "growth" ? x.growth_pct_1d : sort === "sales" ? x[`sales_${period}`] : x[`gmv_cents_${period}`];
    items = items.sort((a, b) => key(b) - key(a));
    const cap = plan.id === "free" ? 10 : Infinity;
    const shown = items.slice(0, Math.min(limit, cap));
    return {
      items: shown.map((x) => ({ ...x, sales: x[`sales_${period}`], gmv_cents: x[`gmv_cents_${period}`], favorite: db.favorites.has(x.id) })),
      locked: plan.id === "free" && items.length > cap,
    } as T;
  }
  if ((r = m(/^\/api\/products\/([^/]+)$/))) {
    const x = db.products.find((y) => y.id === r![1]);
    if (!x) throw new DemoError(404, "Produto não encontrado.");
    return {
      product: { ...x, favorite: db.favorites.has(x.id), sales: x.sales_7d, gmv_cents: x.gmv_cents_7d },
      videos: x.videos.map((v) => ({
        creator_handle: v.creator_handle,
        video_url: "",
        views: String(v.views),
        gmv_cents: String(v.gmv_cents),
        posted_at: new Date(Date.now() - v.days_ago * 86400_000).toISOString().slice(0, 10),
      })),
    } as T;
  }
  if ((r = m(/^\/api\/favorites\/([^/]+)$/))) {
    if (method === "PUT") db.favorites.add(r[1]!);
    else db.favorites.delete(r[1]!);
    return { ok: true } as T;
  }

  throw new DemoError(404, "Essa função só existe no site publicado.");
}

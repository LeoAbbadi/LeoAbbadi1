// Monta o vídeo final (gancho + corpo + CTA) dentro do navegador, sem servidor.
// Usado na demonstração: cada pedaço toca num <canvas> vertical 1080x1920, o som do
// próprio vídeo vai para o Web Audio e o MediaRecorder grava tudo num arquivo só.
// A gravação acontece em tempo real: um vídeo de 25 s leva ~25 s para ficar pronto.
//
// Cuidados com o iPhone (Safari e app do Claude):
// - vídeos precisam estar na página (num "palco" invisível) e receber um play para carregar;
// - o som só sai se o elemento de vídeo e o áudio forem liberados dentro do toque do usuário
//   (prepareForRender), por isso usamos sempre os mesmos 3 elementos de vídeo;
// - o fim do vídeo e o fim da gravação têm prazo: nada fica preso em 99%.

export interface RenderResult {
  blob: Blob;
  ext: "mp4" | "webm";
}

export type RenderPhase = "preparing" | "recording" | "finishing";

const WIDTH = 1080;
const HEIGHT = 1920;
const POOL_SIZE = 3; // gancho, corpo e CTA

function pickMime(): { mime: string; ext: "mp4" | "webm" } {
  // Prioridade: MP4 com H.264 + AAC, que a galeria do celular e o TikTok aceitam.
  // No iPhone/iPad (e Safari) o "video/mp4" puro já é H.264; em outros navegadores ele
  // pode virar VP9 dentro de MP4, então só entra depois do WebM.
  const ua = navigator.userAgent;
  const apple = /iPhone|iPad|iPod/.test(ua) || (/Safari/.test(ua) && !/Chrome|Chromium|CriOS|Android/.test(ua));
  const candidates: [string, "mp4" | "webm"][] = [
    ["video/mp4;codecs=avc1.640028,mp4a.40.2", "mp4"],
    ["video/mp4;codecs=avc1.42E01F,mp4a.40.2", "mp4"],
    ["video/mp4;codecs=avc1,mp4a", "mp4"],
    ["video/mp4;codecs=h264,aac", "mp4"],
    ...(apple ? ([["video/mp4", "mp4"]] as [string, "mp4"][]) : []),
    ["video/webm;codecs=vp9,opus", "webm"],
    ["video/webm;codecs=vp8,opus", "webm"],
    ["video/webm", "webm"],
    ["video/mp4", "mp4"],
  ];
  for (const [mime, ext] of candidates) {
    if (typeof MediaRecorder !== "undefined" && MediaRecorder.isTypeSupported(mime)) return { mime, ext };
  }
  throw new Error("Este navegador não consegue gravar vídeo. Tente pelo Safari ou Chrome atualizados.");
}

// ---------- palco, elementos de vídeo e áudio (liberados no toque) ----------

let stageEl: HTMLDivElement | null = null;
const pool: HTMLVideoElement[] = [];
const elementAudio = new WeakMap<HTMLVideoElement, MediaElementAudioSourceNode>();
const blessed = new WeakSet<HTMLVideoElement>();
let sharedAudio: AudioContext | null = null;

// Palco escondido (mas "visível" para o navegador): o iPhone não carrega nem desenha
// vídeos fora da página ou com display:none.
function stage(): HTMLDivElement {
  if (stageEl?.isConnected) return stageEl;
  const el = document.createElement("div");
  el.setAttribute("aria-hidden", "true");
  el.style.cssText =
    "position:fixed;left:0;top:0;width:2px;height:2px;overflow:hidden;opacity:0.01;pointer-events:none;z-index:-1";
  document.body.appendChild(el);
  stageEl = el;
  return el;
}

function makeVideo(): HTMLVideoElement {
  const v = document.createElement("video");
  v.playsInline = true;
  v.setAttribute("playsinline", "");
  v.preload = "auto";
  v.width = 2;
  v.height = 2;
  stage().appendChild(v);
  return v;
}

function audioContext(): AudioContext {
  const AudioCtx = window.AudioContext ?? (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
  sharedAudio ??= new AudioCtx();
  return sharedAudio;
}

/**
 * Chame DENTRO do toque/clique do usuário, antes de qualquer espera.
 * Libera o áudio e os 3 elementos de vídeo usados na montagem (exigência do iPhone).
 */
export function prepareForRender(): void {
  const ctx = audioContext();
  void ctx.resume();
  try {
    const silence = ctx.createBufferSource();
    silence.buffer = ctx.createBuffer(1, 1, 22050);
    silence.connect(ctx.destination);
    silence.start(0);
  } catch {
    /* sem problema */
  }
  while (pool.length < POOL_SIZE) pool.push(makeVideo());
  for (const v of pool) {
    // o som do vídeo passa a ir só para a gravação, nunca para o alto-falante
    if (!elementAudio.has(v)) {
      try {
        elementAudio.set(v, ctx.createMediaElementSource(v));
      } catch {
        /* sem áudio do elemento: usa o plano B (decodificar o arquivo) */
      }
    }
    // a liberação vale para sempre; não mexe em quem já foi liberado (pode estar montando agora)
    if (blessed.has(v)) continue;
    blessed.add(v);
    v.muted = false;
    try {
      v.load();
      v.play()?.catch(() => undefined);
      v.pause();
    } catch {
      /* só queremos a liberação do toque */
    }
  }
}

// ---------- utilidades ----------

function withTimeout<T>(p: Promise<T>, ms: number, message: string): Promise<T> {
  return new Promise((resolve, reject) => {
    const t = setTimeout(() => reject(new Error(message)), ms);
    p.then(
      (v) => {
        clearTimeout(t);
        resolve(v);
      },
      (e) => {
        clearTimeout(t);
        reject(e);
      },
    );
  });
}

function once(el: HTMLMediaElement, event: string): Promise<void> {
  return new Promise((resolve, reject) => {
    const ok = () => {
      el.removeEventListener("error", fail);
      resolve();
    };
    const fail = () => {
      el.removeEventListener(event, ok);
      reject(new Error("Não foi possível abrir um dos vídeos enviados."));
    };
    el.addEventListener(event, ok, { once: true });
    el.addEventListener("error", fail, { once: true });
  });
}

/**
 * Carrega o pedaço e "acorda" o vídeo (o iPhone só baixa os quadros depois de um play).
 * Devolve se o som pode vir do próprio vídeo.
 */
async function loadInto(v: HTMLVideoElement, url: string): Promise<boolean> {
  v.pause();
  const meta = once(v, "loadedmetadata");
  v.src = url;
  v.load();
  await withTimeout(meta, 20_000, "Um dos vídeos demorou demais para abrir.");
  let soundFromElement = elementAudio.has(v);
  v.muted = !soundFromElement;
  try {
    await withTimeout(v.play(), 8_000, "timeout");
  } catch {
    // o navegador não deixou tocar com som: toca mudo e o som vem do plano B
    soundFromElement = false;
    v.muted = true;
    await withTimeout(v.play(), 8_000, "O navegador não deixou tocar um dos vídeos.");
  }
  v.pause();
  if (v.currentTime > 0) {
    const seeked = once(v, "seeked");
    v.currentTime = 0;
    await withTimeout(seeked, 5_000, "").catch(() => undefined);
  }
  return soundFromElement;
}

async function decodeAudio(ctx: AudioContext, url: string): Promise<AudioBuffer | null> {
  try {
    const data = await (await fetch(url)).arrayBuffer();
    return await ctx.decodeAudioData(data);
  } catch {
    return null; // pedaço sem áudio (ou formato que o navegador não decodifica): fica em silêncio
  }
}

function drawFrame(g: CanvasRenderingContext2D, v: HTMLVideoElement) {
  const vw = v.videoWidth || WIDTH;
  const vh = v.videoHeight || HEIGHT;
  const target = WIDTH / HEIGHT;
  const ratio = vw / vh;
  g.fillStyle = "#000";
  g.fillRect(0, 0, WIDTH, HEIGHT);
  // vertical: preenche a tela; horizontal ou quadrado: encaixa inteiro com faixas pretas
  const scale = Math.abs(ratio - target) / target < 0.12 ? Math.max(WIDTH / vw, HEIGHT / vh) : Math.min(WIDTH / vw, HEIGHT / vh);
  const w = vw * scale;
  const h = vh * scale;
  g.drawImage(v, (WIDTH - w) / 2, (HEIGHT - h) / 2, w, h);
}

/** Espera o pedaço terminar. Se travar no finzinho, considera terminado; se travar no meio, avisa. */
function waitPartEnd(v: HTMLVideoElement, duration: number, onTime: (t: number) => void): Promise<void> {
  return new Promise((resolve, reject) => {
    let last = -1;
    let still = 0;
    const startedAt = Date.now();
    const finish = () => {
      clearInterval(tick);
      v.onended = null;
      resolve();
    };
    const tick = setInterval(() => {
      const t = v.currentTime;
      onTime(t);
      if (v.ended || t >= duration - 0.08) return finish();
      // prazo máximo: a duração do pedaço + 8 s
      if (Date.now() - startedAt > (duration + 8) * 1000) return finish();
      if (t === last) {
        still += 200;
        if (still >= 1500 && t >= duration - 1.2) return finish(); // parou no finzinho
        if (still >= 12_000) {
          clearInterval(tick);
          v.onended = null;
          reject(new Error("A montagem parou. Deixe a tela ligada, com esta página aberta, e tente de novo."));
        }
      } else {
        still = 0;
        last = t;
      }
    }, 200);
    v.onended = finish;
  });
}

// ---------- montagem ----------

/** Monta um vídeo. `onProgress` recebe de 0 a 1 e a etapa atual. */
export async function renderSequence(
  urls: string[],
  onProgress: (p: number, phase: RenderPhase) => void,
): Promise<RenderResult> {
  const audio = audioContext();
  const { mime, ext } = pickMime();
  onProgress(0, "preparing");
  while (pool.length < urls.length) pool.push(makeVideo());
  const videos = urls.map((_, i) => pool[i]!);

  let raf = 0;
  let recorder: MediaRecorder | null = null;
  let stream: MediaStream | null = null;
  let canvas: HTMLCanvasElement | null = null;
  const connected: AudioNode[] = [];
  try {
    const soundFromElement: boolean[] = [];
    for (const [i, v] of videos.entries()) soundFromElement.push(await loadInto(v, urls[i]!));
    // plano B do som: decodificar o arquivo (um de cada vez, para não pesar na memória)
    const buffers: (AudioBuffer | null)[] = [];
    for (const [i, u] of urls.entries()) buffers.push(soundFromElement[i] ? null : await decodeAudio(audio, u));
    const durations = videos.map((v, i) => (Number.isFinite(v.duration) && v.duration > 0 ? v.duration : (buffers[i]?.duration ?? 0)));
    const total = durations.reduce((a, b) => a + b, 0) || 1;

    canvas = document.createElement("canvas");
    canvas.width = WIDTH;
    canvas.height = HEIGHT;
    canvas.style.cssText = "width:2px;height:2px";
    stage().appendChild(canvas);
    const g = canvas.getContext("2d")!;
    drawFrame(g, videos[0]!);

    if (audio.state !== "running") await audio.resume().catch(() => undefined);
    const dest = audio.createMediaStreamDestination();
    stream = new MediaStream([...canvas.captureStream(30).getVideoTracks(), ...dest.stream.getAudioTracks()]);
    recorder = new MediaRecorder(stream, { mimeType: mime, videoBitsPerSecond: 8_000_000, audioBitsPerSecond: 128_000 });
    const chunks: Blob[] = [];
    recorder.ondataavailable = (e) => {
      if (e.data.size) chunks.push(e.data);
    };
    const rec = recorder;
    const stopped = new Promise<void>((resolve) => (rec.onstop = () => resolve()));

    let current = videos[0]!;
    const loop = () => {
      drawFrame(g, current);
      raf = requestAnimationFrame(loop);
    };
    raf = requestAnimationFrame(loop);
    recorder.start(1000);
    onProgress(0, "recording");

    let elapsedBefore = 0;
    for (let i = 0; i < videos.length; i++) {
      const v = videos[i]!;
      current = v;
      v.currentTime = 0;
      let source: AudioBufferSourceNode | null = null;
      const fromElement = soundFromElement[i] ? elementAudio.get(v) : undefined;
      if (fromElement) {
        v.muted = false;
        fromElement.connect(dest);
        connected.push(fromElement);
      } else if (buffers[i]) {
        source = audio.createBufferSource();
        source.buffer = buffers[i]!;
        source.connect(dest);
      }
      await withTimeout(v.play(), 10_000, "O navegador parou de tocar o vídeo. Deixe a tela ligada e tente de novo.");
      source?.start();
      await waitPartEnd(v, durations[i]!, (t) => onProgress(Math.min(0.97, (elapsedBefore + t) / total), "recording"));
      source?.stop();
      v.pause();
      fromElement?.disconnect();
      elapsedBefore += durations[i]!;
    }

    // Fecha o arquivo. Continua desenhando até o fim (o Safari precisa de quadros para
    // terminar de gravar) e não espera para sempre pelo aviso de "parou".
    onProgress(0.98, "finishing");
    try {
      recorder.requestData();
    } catch {
      /* nem todo navegador aceita aqui */
    }
    recorder.stop();
    await Promise.race([stopped, new Promise((r) => setTimeout(r, 6_000))]);
    cancelAnimationFrame(raf);
    const blob = new Blob(chunks, { type: mime.split(";")[0] });
    if (!blob.size) throw new Error("O navegador não conseguiu gravar o vídeo final. Tente de novo.");
    onProgress(1, "finishing");
    return { blob, ext };
  } finally {
    cancelAnimationFrame(raf);
    if (recorder && recorder.state !== "inactive") {
      try {
        recorder.stop();
      } catch {
        /* já parou */
      }
    }
    stream?.getTracks().forEach((t) => t.stop());
    connected.forEach((n) => {
      try {
        n.disconnect();
      } catch {
        /* já desconectado */
      }
    });
    videos.forEach((v) => v.pause());
    canvas?.remove();
  }
}

// ---------- entregar o arquivo ----------

interface Downloads {
  save(req: { filename: string; data: Blob | string }): Promise<unknown>;
}

let downloadsPromise: Promise<Downloads | null> | null = null;
function getDownloads(): Promise<Downloads | null> {
  const claude = (window as unknown as { claude?: { use(name: string): Promise<unknown> } }).claude;
  if (!claude?.use) return Promise.resolve(null);
  downloadsPromise ??= claude.use("downloads") as Promise<Downloads | null>;
  return downloadsPromise;
}

export class SaveError extends Error {}

/**
 * Salva o arquivo. Dentro da prévia do Claude usa o recurso de downloads (o
 * aparelho pede confirmação); fora dela, faz um download comum.
 * Chame a partir de um toque do usuário.
 */
export async function saveFile(filename: string, data: Blob): Promise<"saved" | "declined"> {
  const inViewer = !!(window as unknown as { claude?: { use?: unknown } }).claude?.use;
  if (inViewer) {
    const downloads = await getDownloads();
    if (!downloads) {
      throw new SaveError("Esta página não conseguiu liberar o download neste aparelho. Tente abrir o link pelo app do Claude.");
    }
    try {
      await downloads.save({ filename, data });
      return "saved";
    } catch (err) {
      const code = (err as { code?: string }).code ?? "erro";
      if (code === "declined") return "declined";
      if (code === "rate_limited") throw new SaveError("Já tem um download esperando sua confirmação na tela.");
      if (code === "too_large") throw new SaveError("O arquivo ficou grande demais para salvar por aqui. Baixe menos vídeos de uma vez.");
      throw new SaveError(`Não foi possível salvar o arquivo (${code}).`);
    }
  }
  const url = URL.createObjectURL(data);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 60_000);
  return "saved";
}

/** Pede o recurso de downloads logo ao abrir a página, para o salvar responder rápido. */
export function warmUpDownloads(): void {
  void getDownloads();
}

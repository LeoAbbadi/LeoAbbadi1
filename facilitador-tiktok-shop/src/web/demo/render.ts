// Monta o vídeo final (gancho + corpo + CTA) dentro do navegador, sem servidor.
// Usado na demonstração: cada pedaço toca sem som num <canvas> vertical 1080x1920,
// o áudio é decodificado à parte e mixado, e o MediaRecorder grava o resultado.
// A gravação acontece em tempo real: um vídeo de 25 s leva ~25 s para ficar pronto.

export interface RenderResult {
  blob: Blob;
  ext: "mp4" | "webm";
}

const WIDTH = 1080;
const HEIGHT = 1920;

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

// Palco escondido (mas "visível" para o navegador): o iPhone não carrega nem desenha
// vídeos fora da página ou com display:none.
function stage(): HTMLDivElement {
  const el = document.createElement("div");
  el.setAttribute("aria-hidden", "true");
  el.style.cssText =
    "position:fixed;left:0;top:0;width:2px;height:2px;overflow:hidden;opacity:0.01;pointer-events:none;z-index:-1";
  document.body.appendChild(el);
  return el;
}

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

/** Carrega e "acorda" o vídeo: o iPhone só baixa os quadros depois de um play. */
async function loadVideo(url: string, holder: HTMLElement): Promise<HTMLVideoElement> {
  const v = document.createElement("video");
  v.muted = true;
  v.defaultMuted = true;
  v.playsInline = true;
  v.setAttribute("playsinline", "");
  v.setAttribute("muted", "");
  v.preload = "auto";
  v.width = 2;
  v.height = 2;
  holder.appendChild(v);
  const meta = once(v, "loadedmetadata");
  v.src = url;
  v.load();
  await withTimeout(meta, 20_000, "Um dos vídeos demorou demais para abrir.");
  await withTimeout(v.play(), 10_000, "O navegador não deixou tocar um dos vídeos.");
  v.pause();
  if (v.currentTime > 0) {
    const seeked = once(v, "seeked");
    v.currentTime = 0;
    await withTimeout(seeked, 5_000, "Não foi possível voltar o vídeo ao início.").catch(() => undefined);
  }
  return v;
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
  if (Math.abs(ratio - target) / target < 0.12) {
    // vertical: preenche a tela (corta um pouco das bordas se precisar)
    const scale = Math.max(WIDTH / vw, HEIGHT / vh);
    const w = vw * scale;
    const h = vh * scale;
    g.drawImage(v, (WIDTH - w) / 2, (HEIGHT - h) / 2, w, h);
  } else {
    // horizontal ou quadrado: encaixa inteiro com faixas pretas
    const scale = Math.min(WIDTH / vw, HEIGHT / vh);
    const w = vw * scale;
    const h = vh * scale;
    g.drawImage(v, (WIDTH - w) / 2, (HEIGHT - h) / 2, w, h);
  }
}

let sharedAudio: AudioContext | null = null;

/**
 * Chame dentro do toque/clique do usuário: o iPhone só libera o áudio assim.
 * Depois de liberado, os próximos vídeos da fila também saem com som.
 */
export function unlockAudio(): AudioContext {
  const AudioCtx = window.AudioContext ?? (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
  sharedAudio ??= new AudioCtx();
  void sharedAudio.resume();
  try {
    const silence = sharedAudio.createBufferSource();
    silence.buffer = sharedAudio.createBuffer(1, 1, 22050);
    silence.connect(sharedAudio.destination);
    silence.start(0);
  } catch {
    /* sem problema */
  }
  return sharedAudio;
}

/** Monta um vídeo. `onProgress` recebe de 0 a 1. */
export function renderSequence(urls: string[], onProgress: (p: number) => void): Promise<RenderResult> {
  return run(urls, unlockAudio(), onProgress);
}

async function run(urls: string[], audio: AudioContext, onProgress: (p: number) => void): Promise<RenderResult> {
  const { mime, ext } = pickMime();
  const holder = stage();
  const videos: HTMLVideoElement[] = [];
  let raf = 0;
  let recorder: MediaRecorder | null = null;
  let stream: MediaStream | null = null;
  try {
    for (const u of urls) videos.push(await loadVideo(u, holder));
    // um de cada vez para não estourar a memória do celular com vídeos grandes
    const buffers: (AudioBuffer | null)[] = [];
    for (const u of urls) buffers.push(await decodeAudio(audio, u));
    const durations = videos.map((v, i) => (Number.isFinite(v.duration) && v.duration > 0 ? v.duration : (buffers[i]?.duration ?? 0)));
    const total = durations.reduce((a, b) => a + b, 0) || 1;

    const canvas = document.createElement("canvas");
    canvas.width = WIDTH;
    canvas.height = HEIGHT;
    canvas.style.cssText = "width:2px;height:2px";
    holder.appendChild(canvas);
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

    let elapsedBefore = 0;
    for (let i = 0; i < videos.length; i++) {
      const v = videos[i]!;
      current = v;
      v.currentTime = 0;
      const buffer = buffers[i];
      let source: AudioBufferSourceNode | null = null;
      if (buffer) {
        source = audio.createBufferSource();
        source.buffer = buffer;
        source.connect(dest);
      }
      await withTimeout(v.play(), 10_000, "O navegador parou de tocar o vídeo. Deixe a tela ligada e tente de novo.");
      source?.start();
      // termina no fim do vídeo; se o vídeo travar por 12 s, avisa em vez de ficar parado
      await new Promise<void>((resolve, reject) => {
        let last = -1;
        let still = 0;
        const tick = setInterval(() => {
          onProgress(Math.min(0.99, (elapsedBefore + v.currentTime) / total));
          if (v.ended || v.currentTime >= durations[i]! - 0.05) {
            clearInterval(tick);
            resolve();
            return;
          }
          if (v.currentTime === last) {
            still += 250;
            if (still >= 12_000) {
              clearInterval(tick);
              reject(new Error("A montagem parou. Deixe a tela ligada, com esta página aberta, e tente de novo."));
            }
          } else {
            still = 0;
            last = v.currentTime;
          }
        }, 250);
        v.onended = () => {
          clearInterval(tick);
          resolve();
        };
      });
      source?.stop();
      v.pause();
      elapsedBefore += durations[i]!;
    }
    cancelAnimationFrame(raf);
    recorder.stop();
    await stopped;
    const blob = new Blob(chunks, { type: mime.split(";")[0] });
    if (!blob.size) throw new Error("O navegador não conseguiu gravar o vídeo final.");
    onProgress(1);
    return { blob, ext };
  } finally {
    cancelAnimationFrame(raf);
    if (recorder && recorder.state !== "inactive") recorder.stop();
    stream?.getTracks().forEach((t) => t.stop());
    videos.forEach((v) => {
      v.pause();
      v.removeAttribute("src");
      v.load();
    });
    holder.remove();
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

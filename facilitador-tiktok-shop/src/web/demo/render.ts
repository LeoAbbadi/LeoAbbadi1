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

function loadVideo(url: string): Promise<HTMLVideoElement> {
  return new Promise((resolve, reject) => {
    const v = document.createElement("video");
    v.muted = true;
    v.playsInline = true;
    v.preload = "auto";
    v.crossOrigin = "anonymous";
    v.src = url;
    const done = () => {
      v.removeEventListener("canplaythrough", done);
      resolve(v);
    };
    v.addEventListener("canplaythrough", done);
    v.addEventListener("error", () => reject(new Error("Não foi possível abrir um dos vídeos.")), { once: true });
    v.load();
    // Alguns navegadores de celular só disparam canplaythrough depois de tocar
    setTimeout(() => (v.readyState >= 2 ? done() : undefined), 2500);
  });
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
  return sharedAudio;
}

/** Monta um vídeo. `onProgress` recebe de 0 a 1. */
export function renderSequence(urls: string[], onProgress: (p: number) => void): Promise<RenderResult> {
  return run(urls, unlockAudio(), onProgress);
}

async function run(urls: string[], audio: AudioContext, onProgress: (p: number) => void): Promise<RenderResult> {
  const { mime, ext } = pickMime();
  const [videos, buffers] = await Promise.all([Promise.all(urls.map(loadVideo)), Promise.all(urls.map((u) => decodeAudio(audio, u)))]);
  const durations = videos.map((v, i) => (Number.isFinite(v.duration) && v.duration > 0 ? v.duration : (buffers[i]?.duration ?? 0)));
  const total = durations.reduce((a, b) => a + b, 0) || 1;

  const canvas = document.createElement("canvas");
  canvas.width = WIDTH;
  canvas.height = HEIGHT;
  const g = canvas.getContext("2d")!;
  drawFrame(g, videos[0]!);

  const dest = audio.createMediaStreamDestination();
  const stream = new MediaStream([...canvas.captureStream(30).getVideoTracks(), ...dest.stream.getAudioTracks()]);
  const recorder = new MediaRecorder(stream, { mimeType: mime, videoBitsPerSecond: 8_000_000, audioBitsPerSecond: 128_000 });
  const chunks: Blob[] = [];
  recorder.ondataavailable = (e) => e.data.size && chunks.push(e.data);
  const stopped = new Promise<void>((resolve) => (recorder.onstop = () => resolve()));

  let current = videos[0]!;
  let raf = 0;
  const loop = () => {
    drawFrame(g, current);
    raf = requestAnimationFrame(loop);
  };
  raf = requestAnimationFrame(loop);
  recorder.start(1000);

  let elapsedBefore = 0;
  try {
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
      const ended = new Promise<void>((resolve) => {
        v.onended = () => resolve();
        // garante o fim mesmo se o evento não vier
        setTimeout(resolve, (durations[i]! + 1.5) * 1000);
      });
      await v.play();
      source?.start();
      const tick = setInterval(() => onProgress(Math.min(0.99, (elapsedBefore + v.currentTime) / total)), 250);
      await ended;
      clearInterval(tick);
      source?.stop();
      elapsedBefore += durations[i]!;
    }
  } finally {
    cancelAnimationFrame(raf);
    if (recorder.state !== "inactive") recorder.stop();
    videos.forEach((v) => v.pause());
  }
  await stopped;
  stream.getTracks().forEach((t) => t.stop());
  onProgress(1);
  return { blob: new Blob(chunks, { type: mime.split(";")[0] }), ext };
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

/** Salva o arquivo: pela prévia do Claude (pede confirmação) ou como download comum. */
export async function saveFile(filename: string, data: Blob): Promise<"saved" | "declined"> {
  const downloads = await getDownloads();
  if (downloads) {
    try {
      await downloads.save({ filename, data });
      return "saved";
    } catch (err) {
      const code = (err as { code?: string }).code;
      if (code === "declined") return "declined";
      if (code === "rate_limited") throw new Error("Já tem um download esperando confirmação.");
      if (code !== "unavailable" && code !== "not_granted") throw new Error("Não foi possível salvar o arquivo.");
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

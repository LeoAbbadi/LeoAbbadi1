import { spawn } from "node:child_process";
import fsp from "node:fs/promises";

function run(cmd: string, args: string[]): Promise<string> {
  return new Promise((resolve, reject) => {
    const child = spawn(cmd, args, { stdio: ["ignore", "pipe", "pipe"] });
    let out = "";
    let err = "";
    child.stdout.on("data", (d) => (out += d));
    child.stderr.on("data", (d) => (err = (err + d).slice(-4000)));
    child.on("error", reject);
    child.on("close", (code) => (code === 0 ? resolve(out) : reject(new Error(`${cmd} saiu com código ${code}: ${err}`))));
  });
}

export interface Probe {
  duration: number;
  hasVideo: boolean;
  hasAudio: boolean;
}

export async function probe(file: string): Promise<Probe> {
  const json = JSON.parse(
    await run("ffprobe", ["-v", "error", "-show_entries", "format=duration:stream=codec_type", "-of", "json", file]),
  ) as { format?: { duration?: string }; streams?: { codec_type: string }[] };
  const streams = json.streams ?? [];
  return {
    duration: Number(json.format?.duration ?? 0),
    hasVideo: streams.some((s) => s.codec_type === "video"),
    hasAudio: streams.some((s) => s.codec_type === "audio"),
  };
}

/**
 * Deixa todo pedaço no mesmo formato: vertical 1080x1920, 30fps, H.264 e áudio AAC 48kHz
 * com volume padronizado. Feito uma vez por pedaço; depois a junção é só cópia (barata).
 */
export async function normalize(input: string, output: string): Promise<Probe> {
  const info = await probe(input);
  if (!info.hasVideo) throw new Error("O arquivo enviado não tem vídeo.");
  const args = ["-y", "-v", "error", "-i", input];
  if (!info.hasAudio) args.push("-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo");
  args.push(
    "-map", "0:v:0",
    "-map", info.hasAudio ? "0:a:0" : "1:a:0",
    "-vf", "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=30,format=yuv420p",
    "-af", "loudnorm=I=-14:TP=-1.5:LRA=11,aresample=48000",
    "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-profile:v", "high", "-level", "4.1", "-g", "60",
    "-c:a", "aac", "-b:a", "128k", "-ac", "2",
    "-video_track_timescale", "15360",
    "-movflags", "+faststart",
  );
  if (!info.hasAudio) args.push("-shortest");
  args.push(output);
  await run("ffmpeg", args);
  return probe(output);
}

/** Junta pedaços já normalizados sem recodificar. */
export async function concat(parts: string[], output: string, listFile: string): Promise<void> {
  await fsp.writeFile(listFile, parts.map((p) => `file '${p.replace(/'/g, "'\\''")}'`).join("\n"));
  await run("ffmpeg", ["-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", listFile, "-c", "copy", "-movflags", "+faststart", output]);
}

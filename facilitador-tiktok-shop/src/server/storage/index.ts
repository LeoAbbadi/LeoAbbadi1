// Onde os vídeos ficam guardados.
// - "s3": Cloudflare R2 (recomendado: não cobra pelo download), AWS S3 ou outro S3 compatível.
//   O navegador envia e baixa direto do bucket por links assinados; o servidor não carrega o vídeo.
// - "local": pasta ./data, para desenvolvimento.
import crypto from "node:crypto";
import fs from "node:fs";
import fsp from "node:fs/promises";
import path from "node:path";
import { pipeline } from "node:stream/promises";
import type { Readable } from "node:stream";
import {
  DeleteObjectsCommand,
  GetObjectCommand,
  HeadObjectCommand,
  PutObjectCommand,
  S3Client,
} from "@aws-sdk/client-s3";
import { getSignedUrl } from "@aws-sdk/s3-request-presigner";
import { config } from "../config.ts";

export interface Storage {
  /** link para o navegador enviar o arquivo com PUT */
  uploadUrl(key: string, contentType: string): Promise<string>;
  /** link temporário para baixar/assistir */
  downloadUrl(key: string, filename?: string): Promise<string>;
  putFile(key: string, localPath: string, contentType: string): Promise<void>;
  getFile(key: string, localPath: string): Promise<void>;
  size(key: string): Promise<number | null>;
  remove(keys: string[]): Promise<void>;
}

const LINK_TTL_S = 60 * 60 * 6;

// ---------- local ----------

function sign(key: string, method: string, exp: number): string {
  return crypto.createHmac("sha256", config.sessionSecret).update(`${method}:${key}:${exp}`).digest("hex");
}

export function verifyLocalSignature(key: string, method: string, exp: number, sig: string): boolean {
  if (!Number.isFinite(exp) || exp < Date.now() / 1000) return false;
  const expected = Buffer.from(sign(key, method, exp));
  const given = Buffer.from(sig);
  return expected.length === given.length && crypto.timingSafeEqual(expected, given);
}

export function localPathFor(key: string): string {
  const full = path.resolve(config.localDataDir, key);
  if (!full.startsWith(config.localDataDir + path.sep)) throw new Error("chave inválida");
  return full;
}

class LocalStorage implements Storage {
  private link(key: string, method: string, extra = ""): string {
    const exp = Math.floor(Date.now() / 1000) + LINK_TTL_S;
    return `/api/files/${encodeURI(key)}?exp=${exp}&sig=${sign(key, method, exp)}${extra}`;
  }
  async uploadUrl(key: string): Promise<string> {
    return this.link(key, "PUT");
  }
  async downloadUrl(key: string, filename?: string): Promise<string> {
    return this.link(key, "GET", filename ? `&name=${encodeURIComponent(filename)}` : "");
  }
  async putFile(key: string, localPath: string): Promise<void> {
    const dest = localPathFor(key);
    await fsp.mkdir(path.dirname(dest), { recursive: true });
    await fsp.copyFile(localPath, dest);
  }
  async getFile(key: string, localPath: string): Promise<void> {
    await fsp.copyFile(localPathFor(key), localPath);
  }
  async size(key: string): Promise<number | null> {
    try {
      return (await fsp.stat(localPathFor(key))).size;
    } catch {
      return null;
    }
  }
  async remove(keys: string[]): Promise<void> {
    await Promise.all(keys.map((k) => fsp.rm(localPathFor(k), { force: true })));
  }
  async writeStream(key: string, body: Readable, maxBytes: number): Promise<number> {
    const dest = localPathFor(key);
    await fsp.mkdir(path.dirname(dest), { recursive: true });
    let written = 0;
    body.on("data", (chunk: Buffer) => {
      written += chunk.length;
      if (written > maxBytes) body.destroy(new Error("arquivo grande demais"));
    });
    await pipeline(body, fs.createWriteStream(dest));
    return written;
  }
}

// ---------- S3 / R2 ----------

class S3Storage implements Storage {
  private client = new S3Client({
    region: config.s3.region,
    endpoint: config.s3.endpoint || undefined,
    credentials: { accessKeyId: config.s3.accessKeyId, secretAccessKey: config.s3.secretAccessKey },
  });
  private bucket = config.s3.bucket;

  uploadUrl(key: string, contentType: string): Promise<string> {
    return getSignedUrl(this.client, new PutObjectCommand({ Bucket: this.bucket, Key: key, ContentType: contentType }), {
      expiresIn: LINK_TTL_S,
    });
  }
  downloadUrl(key: string, filename?: string): Promise<string> {
    return getSignedUrl(
      this.client,
      new GetObjectCommand({
        Bucket: this.bucket,
        Key: key,
        ResponseContentDisposition: filename ? `attachment; filename="${filename}"` : undefined,
      }),
      { expiresIn: LINK_TTL_S },
    );
  }
  async putFile(key: string, localPath: string, contentType: string): Promise<void> {
    const stat = await fsp.stat(localPath);
    await this.client.send(
      new PutObjectCommand({
        Bucket: this.bucket,
        Key: key,
        Body: fs.createReadStream(localPath),
        ContentLength: stat.size,
        ContentType: contentType,
      }),
    );
  }
  async getFile(key: string, localPath: string): Promise<void> {
    const res = await this.client.send(new GetObjectCommand({ Bucket: this.bucket, Key: key }));
    await pipeline(res.Body as Readable, fs.createWriteStream(localPath));
  }
  async size(key: string): Promise<number | null> {
    try {
      const res = await this.client.send(new HeadObjectCommand({ Bucket: this.bucket, Key: key }));
      return res.ContentLength ?? null;
    } catch {
      return null;
    }
  }
  async remove(keys: string[]): Promise<void> {
    for (let i = 0; i < keys.length; i += 1000) {
      const chunk = keys.slice(i, i + 1000);
      if (!chunk.length) continue;
      await this.client.send(
        new DeleteObjectsCommand({ Bucket: this.bucket, Delete: { Objects: chunk.map((Key) => ({ Key })) } }),
      );
    }
  }
}

export const storage: Storage = config.storageDriver === "s3" ? new S3Storage() : new LocalStorage();
export const localStorage = storage instanceof LocalStorage ? storage : null;

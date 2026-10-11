import path from "node:path";

function str(name: string, fallback = ""): string {
  return process.env[name]?.trim() || fallback;
}

export const config = {
  appUrl: str("APP_URL", "http://localhost:5173"),
  port: Number(str("PORT", "3000")),
  databaseUrl: str("DATABASE_URL", "postgres://fts:fts@localhost:5432/fts"),
  sessionSecret: str("SESSION_SECRET"),
  isProduction: process.env.NODE_ENV === "production",

  storageDriver: str("STORAGE_DRIVER", "local") as "local" | "s3",
  localDataDir: path.resolve(str("LOCAL_DATA_DIR", "data")),
  s3: {
    endpoint: str("S3_ENDPOINT"),
    region: str("S3_REGION", "auto"),
    bucket: str("S3_BUCKET"),
    accessKeyId: str("S3_ACCESS_KEY_ID"),
    secretAccessKey: str("S3_SECRET_ACCESS_KEY"),
  },

  anthropicApiKey: str("ANTHROPIC_API_KEY"),
  anthropicModel: str("ANTHROPIC_MODEL", "claude-opus-5-5"),

  // true = sem Stripe, o botão de assinar ativa o plano na hora (só para testes)
  demoBilling: str("DEMO_BILLING") === "true",
  stripe: {
    secretKey: str("STRIPE_SECRET_KEY"),
    webhookSecret: str("STRIPE_WEBHOOK_SECRET"),
    prices: {
      starter_monthly: str("STRIPE_PRICE_STARTER_MONTHLY"),
      pro_monthly: str("STRIPE_PRICE_PRO_MONTHLY"),
      pro_annual: str("STRIPE_PRICE_PRO_ANNUAL"),
    } as Record<string, string>,
  },

  workerConcurrency: Number(str("WORKER_CONCURRENCY", "1")),
  // true = o próprio servidor do site também monta os vídeos (um serviço só, bom para testar de graça)
  embeddedWorker: str("EMBEDDED_WORKER") === "true",
  outputRetentionDays: Number(str("OUTPUT_RETENTION_DAYS", "7")),
  adminEmails: str("ADMIN_EMAILS")
    .split(",")
    .map((e) => e.trim().toLowerCase())
    .filter(Boolean),
};

if (!config.sessionSecret) {
  if (config.isProduction) throw new Error("Defina SESSION_SECRET no ambiente.");
  config.sessionSecret = "dev-secret-local";
}

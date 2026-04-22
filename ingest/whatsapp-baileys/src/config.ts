import "dotenv/config";

function req(name: string): string {
  const v = process.env[name];
  if (!v) throw new Error(`Missing required env var: ${name}`);
  return v;
}

function opt(name: string, fallback: string): string {
  return process.env[name] ?? fallback;
}

function intEnv(name: string, fallback: number): number {
  const raw = process.env[name];
  if (!raw) return fallback;
  const n = parseInt(raw, 10);
  if (Number.isNaN(n)) throw new Error(`Env ${name} must be an integer, got ${raw}`);
  return n;
}

export const config = {
  webhookUrl: req("WATCHMATCH_WEBHOOK_URL"),
  hmacSecret: req("WATCHMATCH_HMAC_SECRET"),
  sourceAccount: opt("WA_SOURCE_ACCOUNT", "baileys-default"),
  authDir: opt("WA_AUTH_DIR", "./auth"),
  groupAllowlist: (process.env.WA_GROUP_IDS ?? "")
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean),
  batchMaxSize: intEnv("WA_BATCH_MAX_SIZE", 20),
  batchFlushMs: intEnv("WA_BATCH_FLUSH_MS", 500),
  forwardOwn: opt("WA_FORWARD_OWN", "false") === "true",
  logLevel: opt("WA_LOG_LEVEL", "info"),
} as const;

import crypto from "node:crypto";
import pino from "pino";
import { config } from "./config.js";

const log = pino({ level: config.logLevel, name: "forwarder" });

export interface IncomingMessage {
  external_message_id: string;
  external_group_id: string;
  group_name?: string | null;
  sender_name?: string | null;
  sender_external_id?: string | null;
  text_body: string;
  message_type: string;
  original_timestamp: string;
  metadata?: Record<string, unknown>;
}

interface Batch {
  source_account: string;
  messages: IncomingMessage[];
}

const queue: IncomingMessage[] = [];
let flushTimer: NodeJS.Timeout | null = null;
let inflight = false;

export function enqueue(msg: IncomingMessage): void {
  queue.push(msg);
  if (queue.length >= config.batchMaxSize) {
    void flush();
  } else if (!flushTimer) {
    flushTimer = setTimeout(() => void flush(), config.batchFlushMs);
  }
}

export async function flush(): Promise<void> {
  if (flushTimer) {
    clearTimeout(flushTimer);
    flushTimer = null;
  }
  if (queue.length === 0 || inflight) return;
  inflight = true;
  const messages = queue.splice(0, config.batchMaxSize);
  try {
    await postWithRetry({ source_account: config.sourceAccount, messages });
  } finally {
    inflight = false;
  }
  if (queue.length > 0) {
    setImmediate(() => void flush());
  }
}

async function postWithRetry(batch: Batch, attempt = 0): Promise<void> {
  const body = JSON.stringify(batch);
  const signature = crypto
    .createHmac("sha256", config.hmacSecret)
    .update(body)
    .digest("hex");

  try {
    const res = await fetch(config.webhookUrl, {
      method: "POST",
      headers: {
        "content-type": "application/json",
        "x-signature": signature,
      },
      body,
    });
    if (!res.ok) {
      const text = await res.text();
      throw new Error(`HTTP ${res.status}: ${text.slice(0, 200)}`);
    }
    log.info({ count: batch.messages.length }, "batch_forwarded");
  } catch (err) {
    if (attempt >= 5) {
      log.error({ err, count: batch.messages.length }, "dropping_batch_after_retries");
      return;
    }
    const delay = Math.min(30000, 500 * 2 ** attempt);
    log.warn({ err: (err as Error).message, attempt, delay }, "retry_scheduled");
    await new Promise((r) => setTimeout(r, delay));
    await postWithRetry(batch, attempt + 1);
  }
}

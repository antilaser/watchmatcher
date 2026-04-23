import {
  default as makeWASocket,
  Browsers,
  DisconnectReason,
  useMultiFileAuthState,
  fetchLatestBaileysVersion,
  type WASocket,
  type WAMessage,
} from "@whiskeysockets/baileys";
import { Boom } from "@hapi/boom";
import qrcode from "qrcode-terminal";
import pino from "pino";

import { config } from "./config.js";
import { enqueue, flush } from "./forwarder.js";

const log = pino({ level: config.logLevel, name: "wa-ingest" });

/** 408 is both `connectionLost` and `timedOut` in Baileys enum */
function disconnectLabel(code: number | undefined): string {
  if (code === undefined) return "unknown";
  const names = Object.entries(DisconnectReason).filter(([, v]) => v === code).map(([k]) => k);
  return names.length ? names.join("|") : `code_${code}`;
}

let currentSocket: WASocket | null = null;

function shouldForward(msg: WAMessage): boolean {
  if (!msg.message) return false;
  if (msg.key.fromMe && !config.forwardOwn) return false;
  const remoteJid = msg.key.remoteJid;
  if (!remoteJid?.endsWith("@g.us")) return false;
  if (config.groupAllowlist.length > 0 && !config.groupAllowlist.includes(remoteJid)) {
    return false;
  }
  return true;
}

function extractText(msg: WAMessage): string | null {
  const m = msg.message;
  if (!m) return null;
  return (
    m.conversation ??
    m.extendedTextMessage?.text ??
    m.imageMessage?.caption ??
    m.videoMessage?.caption ??
    null
  );
}

async function start(): Promise<void> {
  if (currentSocket) {
    try {
      currentSocket.end(undefined);
    } catch {
      /* ignore */
    }
    currentSocket = null;
  }

  const { state, saveCreds } = await useMultiFileAuthState(config.authDir);
  const { version, isLatest } = await fetchLatestBaileysVersion();
  log.info({ version, isLatest }, "baileys_starting");

  const groupNameCache = new Map<string, string>();

  const sock = makeWASocket({
    version,
    auth: state,
    logger: pino({ level: "warn" }),
    browser: Browsers.macOS("Chrome"),
    connectTimeoutMs: 90_000,
    defaultQueryTimeoutMs: 120_000,
    keepAliveIntervalMs: 20_000,
    qrTimeout: 180_000,
    markOnlineOnConnect: false,
    syncFullHistory: false,
    shouldSyncHistoryMessage: () => false,
  });
  currentSocket = sock;

  sock.ev.on("creds.update", saveCreds);

  sock.ev.on("connection.update", (update) => {
    const { connection, lastDisconnect, qr } = update;
    if (qr) {
      log.info("QR received -- scan with WhatsApp on your phone");
      qrcode.generate(qr, { small: true });
    }
    if (connection === "close") {
      const boom = lastDisconnect?.error as Boom | undefined;
      const code = boom?.output?.statusCode;
      const reconnect = code !== DisconnectReason.loggedOut;
      const reason = disconnectLabel(code);
      log.warn(
        { code, reason, reconnect, detail: boom?.message },
        "connection_closed",
      );
      if (reconnect) {
        const delayMs = code === 408 ? 12_000 : 3_000;
        log.info({ delayMs }, "reconnect_scheduled");
        setTimeout(() => void start(), delayMs);
      }
    } else if (connection === "open") {
      log.info("connection_open");
    }
  });

  sock.ev.on("messages.upsert", async ({ messages, type }) => {
    if (type !== "notify") return;
    for (const m of messages) {
      if (!shouldForward(m)) continue;
      const text = extractText(m);
      if (!text) continue;
      const remoteJid = m.key.remoteJid!;

      let groupName = groupNameCache.get(remoteJid) ?? null;
      if (!groupName) {
        try {
          const meta = await sock.groupMetadata(remoteJid);
          groupName = meta.subject;
          groupNameCache.set(remoteJid, groupName);
        } catch {
          // metadata fetch can rate-limit; ignore and forward without name
        }
      }

      const tsSec = Number(m.messageTimestamp) || Math.floor(Date.now() / 1000);
      enqueue({
        external_message_id: m.key.id ?? `${remoteJid}:${tsSec}`,
        external_group_id: remoteJid,
        group_name: groupName,
        sender_name: m.pushName ?? null,
        sender_external_id: m.key.participant ?? remoteJid,
        text_body: text,
        message_type: "text",
        original_timestamp: new Date(tsSec * 1000).toISOString(),
        metadata: { fromMe: m.key.fromMe ?? false },
      });
    }
  });
}

const shutdown = async (signal: string): Promise<void> => {
  log.info({ signal }, "shutdown_flushing_queue");
  await flush();
  process.exit(0);
};

process.on("SIGINT", () => void shutdown("SIGINT"));
process.on("SIGTERM", () => void shutdown("SIGTERM"));

start().catch((err) => {
  log.error({ err }, "fatal");
  process.exit(1);
});

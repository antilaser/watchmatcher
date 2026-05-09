import {
  default as makeWASocket,
  Browsers,
  DisconnectReason,
  downloadMediaMessage,
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
const waLogger = pino({ level: "silent" });
const MAX_IMAGE_BYTES = 5 * 1024 * 1024;

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
    m.documentMessage?.caption ??
    null
  );
}

function inferMessageType(msg: WAMessage): string {
  const m = msg.message;
  if (!m) return "text";
  if (m.imageMessage) return "image";
  if (m.videoMessage) return "video";
  if (m.documentMessage) {
    const mime = m.documentMessage.mimetype || "";
    if (mime.startsWith("image/")) return "image";
    return "document";
  }
  return "text";
}

function quotedMessageMetadata(msg: WAMessage): Record<string, string> {
  const m = msg.message;
  const contextInfo =
    m?.extendedTextMessage?.contextInfo ??
    m?.imageMessage?.contextInfo ??
    m?.videoMessage?.contextInfo ??
    m?.documentMessage?.contextInfo;
  const quotedId = contextInfo?.stanzaId;
  if (!quotedId) return {};
  return {
    quoted_message_id: quotedId,
    ...(contextInfo?.participant ? { quoted_participant: contextInfo.participant } : {}),
    ...(contextInfo?.remoteJid ? { quoted_remote_jid: contextInfo.remoteJid } : {}),
  };
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
  const groupInviteCache = new Map<string, string | undefined>();

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
      const caption = extractText(m)?.trim() ?? "";
      const doc = m.message?.documentMessage;
      const isImageDocument = Boolean(doc?.mimetype?.startsWith("image/"));
      const hasImage = Boolean(m.message?.imageMessage) || isImageDocument;
      let imageBase64: string | undefined;
      let imageMimeType: string | undefined;
      if (hasImage) {
        try {
          const buf = await downloadMediaMessage(m, "buffer", {}, {
            // eslint-disable-next-line @typescript-eslint/no-explicit-any
            logger: waLogger as any,
            reuploadRequest: sock.updateMediaMessage,
          });
          if (buf.length > MAX_IMAGE_BYTES) {
            log.warn({ bytes: buf.length }, "image_too_large_skipped");
          } else {
            imageBase64 = Buffer.from(buf).toString("base64");
            imageMimeType =
              m.message?.imageMessage?.mimetype ??
              doc?.mimetype ??
              "image/jpeg";
          }
        } catch (err) {
          log.warn({ err }, "image_download_failed");
        }
      }
      if (!caption && !imageBase64) continue;
      const remoteJid = m.key.remoteJid!;

      let groupName = groupNameCache.get(remoteJid) ?? null;
      let inviteCode = groupInviteCache.get(remoteJid);
      if (groupName === null || inviteCode === undefined) {
        try {
          const meta = await sock.groupMetadata(remoteJid);
          groupName = meta.subject;
          groupNameCache.set(remoteJid, groupName);
          inviteCode = meta.inviteCode;
          if (!inviteCode) {
            try {
              inviteCode = await sock.groupInviteCode(remoteJid);
            } catch {
              // Some groups/accounts may not allow invite-code lookup.
            }
          }
          groupInviteCache.set(remoteJid, inviteCode);
        } catch {
          // metadata fetch can rate-limit; ignore and forward without name
        }
      }

      const tsSec = Number(m.messageTimestamp) || Math.floor(Date.now() / 1000);
      enqueue({
        external_message_id: m.key.id ?? `${remoteJid}:${tsSec}`,
        external_group_id: remoteJid,
        group_name: groupName,
        group_invite_code: inviteCode ?? undefined,
        sender_name: m.pushName ?? null,
        sender_external_id: m.key.participant ?? remoteJid,
        text_body: caption,
        message_type: inferMessageType(m),
        original_timestamp: new Date(tsSec * 1000).toISOString(),
        metadata: {
          fromMe: m.key.fromMe ?? false,
          ...quotedMessageMetadata(m),
          ...(doc?.mimetype ? { document_mimetype: doc.mimetype } : {}),
          ...(isImageDocument ? { image_sent_as_document: true } : {}),
        },
        image_base64: imageBase64,
        image_mime_type: imageMimeType,
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

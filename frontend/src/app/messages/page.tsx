"use client";

import { useCallback, useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";
import type { Page, RawMessageOut } from "@/lib/types";

export default function MessagesPage() {
  const [offset, setOffset] = useState(0);
  const [data, setData] = useState<Page<RawMessageOut> | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const q = new URLSearchParams();
      q.set("limit", "50");
      q.set("offset", String(offset));
      const page = await apiFetch<Page<RawMessageOut>>(`/messages?${q.toString()}`);
      setData(page);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load");
      setData(null);
    } finally {
      setLoading(false);
    }
  }, [offset]);

  useEffect(() => {
    void load();
  }, [load]);

  async function reprocess(messageId: string) {
    setBusyId(messageId);
    setError(null);
    try {
      await apiFetch(`/messages/${messageId}/reprocess`, { method: "POST", body: "{}" });
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed");
    } finally {
      setBusyId(null);
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="text-2xl font-semibold">Messages</h1>
          <p className="mt-1 text-sm text-slate-400">Raw ingested messages (newest first)</p>
        </div>
        <button
          type="button"
          onClick={() => void load()}
          className="self-start rounded-md border border-surface-border bg-surface-raised px-3 py-2 text-sm hover:bg-surface-border"
        >
          Refresh
        </button>
      </div>

      {error && (
        <div className="rounded-md border border-red-900/50 bg-red-950/40 px-4 py-3 text-sm text-red-200">
          {error}
        </div>
      )}

      {loading && !data ? (
        <p className="text-slate-400">Loading…</p>
      ) : data && data.items.length === 0 ? (
        <p className="text-slate-400">No messages yet.</p>
      ) : (
        <ul className="space-y-3">
          {data?.items.map((m) => (
            <li
              key={m.id}
              className="rounded-lg border border-surface-border bg-surface-raised p-4"
            >
              <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-slate-500">
                <span>
                  {m.sender_name ?? "Unknown"} · {new Date(m.original_timestamp).toLocaleString()}
                </span>
                <span className="font-mono text-slate-400">{m.processing_status}</span>
              </div>
              <p className="mt-2 whitespace-pre-wrap break-words text-sm text-slate-200">{m.text_body}</p>
              <div className="mt-3 flex flex-wrap gap-2">
                <button
                  type="button"
                  disabled={busyId === m.id}
                  onClick={() => void reprocess(m.id)}
                  className="rounded-md border border-surface-border px-3 py-1.5 text-xs hover:bg-surface-border"
                >
                  Reprocess
                </button>
                {m.processing_error && (
                  <p className="text-xs text-red-300/90">{m.processing_error}</p>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}

      {data && data.total > data.limit && (
        <div className="flex gap-3 text-sm">
          <button
            type="button"
            disabled={offset === 0}
            onClick={() => setOffset((o) => Math.max(0, o - data.limit))}
            className="text-accent hover:underline disabled:opacity-40"
          >
            Previous page
          </button>
          <span className="text-slate-500">
            {offset + 1}–{Math.min(offset + data.items.length, data.total)} of {data.total}
          </span>
          <button
            type="button"
            disabled={offset + data.items.length >= data.total}
            onClick={() => setOffset((o) => o + data.limit)}
            className="text-accent hover:underline disabled:opacity-40"
          >
            Next page
          </button>
        </div>
      )}
    </div>
  );
}

"use client";

import { useCallback, useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";
import { alertSummary } from "@/lib/alertText";
import type { AlertOut, Page } from "@/lib/types";

const statuses = ["", "PENDING", "SENT", "ACKNOWLEDGED", "FAILED"] as const;

export default function AlertsPage() {
  const [status, setStatus] = useState<string>("");
  const [offset, setOffset] = useState(0);
  const [data, setData] = useState<Page<AlertOut> | null>(null);
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
      if (status) q.set("status", status);
      const page = await apiFetch<Page<AlertOut>>(`/alerts?${q.toString()}`);
      setData(page);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load");
      setData(null);
    } finally {
      setLoading(false);
    }
  }, [offset, status]);

  useEffect(() => {
    void load();
  }, [load]);

  async function acknowledge(alertId: string) {
    setBusyId(alertId);
    setError(null);
    try {
      await apiFetch(`/alerts/${alertId}/acknowledge`, { method: "POST", body: "{}" });
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed");
    } finally {
      setBusyId(null);
    }
  }

  async function snooze(alertId: string, minutes: number) {
    setBusyId(alertId);
    setError(null);
    try {
      await apiFetch(`/alerts/${alertId}/snooze`, {
        method: "POST",
        body: JSON.stringify({ minutes }),
      });
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
          <h1 className="text-2xl font-semibold">Alerts</h1>
          <p className="mt-1 text-sm text-slate-400">
            Same summaries as Telegram; acknowledge here when needed
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <select
            value={status}
            onChange={(e) => {
              setOffset(0);
              setStatus(e.target.value);
            }}
            className="rounded-md border border-surface-border bg-surface-raised px-3 py-2 text-sm"
          >
            {statuses.map((s) => (
              <option key={s || "all"} value={s}>
                {s || "All statuses"}
              </option>
            ))}
          </select>
          <button
            type="button"
            onClick={() => void load()}
            className="rounded-md border border-surface-border bg-surface-raised px-3 py-2 text-sm hover:bg-surface-border"
          >
            Refresh
          </button>
        </div>
      </div>

      {error && (
        <div className="rounded-md border border-red-900/50 bg-red-950/40 px-4 py-3 text-sm text-red-200">
          {error}
        </div>
      )}

      {loading && !data ? (
        <p className="text-slate-400">Loading…</p>
      ) : data && data.items.length === 0 ? (
        <p className="text-slate-400">No alerts for this filter.</p>
      ) : (
        <ul className="space-y-4">
          {data?.items.map((a) => (
            <li
              key={a.id}
              className="rounded-lg border border-surface-border bg-surface-raised p-4 shadow-sm"
            >
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div className="space-y-1">
                  <div className="flex flex-wrap gap-2 text-xs">
                    <span className="rounded bg-surface-border px-2 py-0.5 font-mono text-slate-300">
                      {a.alert_type}
                    </span>
                    <span className="rounded bg-surface-border px-2 py-0.5 font-mono text-slate-300">
                      {a.channel}
                    </span>
                    <span className="rounded bg-surface-border px-2 py-0.5 font-mono text-slate-300">
                      {a.status}
                    </span>
                    <span className="text-slate-500">{new Date(a.created_at).toLocaleString()}</span>
                  </div>
                  {a.match_id && (
                    <p className="text-xs text-slate-500">
                      Match id:{" "}
                      <a href="/matches" className="font-mono text-accent hover:underline">
                        {a.match_id}
                      </a>
                    </p>
                  )}
                </div>
                <div className="flex flex-wrap gap-2">
                  <button
                    type="button"
                    disabled={busyId === a.id}
                    onClick={() => void acknowledge(a.id)}
                    className="rounded-md border border-surface-border px-3 py-1.5 text-xs hover:bg-surface-border"
                  >
                    Acknowledge
                  </button>
                  <button
                    type="button"
                    disabled={busyId === a.id}
                    onClick={() => void snooze(a.id, 60)}
                    className="rounded-md border border-surface-border px-3 py-1.5 text-xs hover:bg-surface-border"
                  >
                    Snooze 1h
                  </button>
                </div>
              </div>
              <pre className="mt-3 whitespace-pre-wrap break-words font-sans text-sm leading-relaxed text-slate-200">
                {alertSummary(a.payload_json)}
              </pre>
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

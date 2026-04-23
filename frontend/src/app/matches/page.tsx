"use client";

import { useCallback, useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";
import type { MatchOut, Page } from "@/lib/types";

const statuses = ["", "PENDING_REVIEW", "APPROVED", "REJECTED", "EXPIRED"] as const;

export default function MatchesPage() {
  const [status, setStatus] = useState<string>("");
  const [profitableOnly, setProfitableOnly] = useState(false);
  const [offset, setOffset] = useState(0);
  const [data, setData] = useState<Page<MatchOut> | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [actionId, setActionId] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const q = new URLSearchParams();
      q.set("limit", "50");
      q.set("offset", String(offset));
      if (status) q.set("status", status);
      if (profitableOnly) q.set("profitable_only", "true");
      const page = await apiFetch<Page<MatchOut>>(`/matches?${q.toString()}`);
      setData(page);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load");
      setData(null);
    } finally {
      setLoading(false);
    }
  }, [offset, status, profitableOnly]);

  useEffect(() => {
    void load();
  }, [load]);

  async function act(matchId: string, path: "approve" | "reject") {
    setActionId(matchId);
    setError(null);
    try {
      await apiFetch(`/matches/${matchId}/${path}`, { method: "POST", body: "{}" });
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Action failed");
    } finally {
      setActionId(null);
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="text-2xl font-semibold">Matches</h1>
          <p className="mt-1 text-sm text-slate-400">Approve or reject from the browser</p>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <label className="flex items-center gap-2 text-sm text-slate-300">
            <input
              type="checkbox"
              checked={profitableOnly}
              onChange={(e) => {
                setOffset(0);
                setProfitableOnly(e.target.checked);
              }}
              className="rounded border-surface-border bg-surface-raised"
            />
            Profitable only
          </label>
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
        <p className="text-slate-400">No matches for this filter.</p>
      ) : (
        <div className="overflow-x-auto rounded-lg border border-surface-border">
          <table className="w-full min-w-[720px] text-left text-sm">
            <thead className="border-b border-surface-border bg-surface-raised text-slate-400">
              <tr>
                <th className="px-3 py-2 font-medium">Status</th>
                <th className="px-3 py-2 font-medium">Type</th>
                <th className="px-3 py-2 font-medium">Confidence</th>
                <th className="px-3 py-2 font-medium">Profit</th>
                <th className="px-3 py-2 font-medium">Prices</th>
                <th className="px-3 py-2 font-medium">Created</th>
                <th className="px-3 py-2 font-medium">Actions</th>
              </tr>
            </thead>
            <tbody>
              {data?.items.map((m) => (
                <tr key={m.id} className="border-b border-surface-border/60 hover:bg-surface-raised/50">
                  <td className="px-3 py-2 font-mono text-xs text-slate-300">{m.status}</td>
                  <td className="px-3 py-2">{m.match_type}</td>
                  <td className="px-3 py-2">{(m.match_confidence * 100).toFixed(0)}%</td>
                  <td className="px-3 py-2 text-slate-300">
                    {m.expected_profit != null ? `${m.expected_profit}` : "—"}
                  </td>
                  <td className="max-w-[200px] truncate px-3 py-2 text-slate-400" title={`sell ${m.seller_price} / buy ${m.buyer_price}`}>
                    {m.seller_price ?? "—"} / {m.buyer_price ?? "—"}
                  </td>
                  <td className="px-3 py-2 text-xs text-slate-500">
                    {new Date(m.created_at).toLocaleString()}
                  </td>
                  <td className="px-3 py-2">
                    <div className="flex flex-wrap gap-1">
                      <button
                        type="button"
                        disabled={actionId === m.id || m.status !== "PENDING_REVIEW"}
                        onClick={() => void act(m.id, "approve")}
                        className="rounded bg-emerald-900/60 px-2 py-1 text-xs text-emerald-100 hover:bg-emerald-800/60 disabled:opacity-40"
                      >
                        Approve
                      </button>
                      <button
                        type="button"
                        disabled={actionId === m.id || m.status !== "PENDING_REVIEW"}
                        onClick={() => void act(m.id, "reject")}
                        className="rounded bg-red-900/50 px-2 py-1 text-xs text-red-100 hover:bg-red-800/50 disabled:opacity-40"
                      >
                        Reject
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {data && data.total > data.limit && (
        <div className="flex gap-3 text-sm">
          <button
            type="button"
            disabled={offset === 0}
            onClick={() => setOffset((o) => Math.max(0, o - data.limit))}
            className="text-accent hover:underline disabled:opacity-40 disabled:no-underline"
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
            className="text-accent hover:underline disabled:opacity-40 disabled:no-underline"
          >
            Next page
          </button>
        </div>
      )}
    </div>
  );
}

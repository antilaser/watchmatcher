import Link from "next/link";

export default function HomePage() {
  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Dashboard</h1>
        <p className="mt-2 max-w-xl text-slate-400">
          Matches, alert summaries (same text as Telegram), and raw messages. Intended to run on your server behind
          nginx with <code className="text-sm">/</code> for this UI and <code className="text-sm">/api/v1</code> for the
          API (same origin). Set{" "}
          <code className="rounded bg-surface-border px-1.5 py-0.5 text-sm">NEXT_PUBLIC_API_BASE_URL</code> only if the
          API is on a different host than this page.
        </p>
      </div>
      <ul className="grid gap-4 sm:grid-cols-3">
        <li>
          <Link
            href="/matches"
            className="block rounded-lg border border-surface-border bg-surface-raised p-5 transition-colors hover:border-accent/40"
          >
            <h2 className="font-medium text-white">Matches</h2>
            <p className="mt-1 text-sm text-slate-400">Review and approve or reject</p>
          </Link>
        </li>
        <li>
          <Link
            href="/alerts"
            className="block rounded-lg border border-surface-border bg-surface-raised p-5 transition-colors hover:border-accent/40"
          >
            <h2 className="font-medium text-white">Alerts</h2>
            <p className="mt-1 text-sm text-slate-400">Same payloads as Telegram notifications</p>
          </Link>
        </li>
        <li>
          <Link
            href="/messages"
            className="block rounded-lg border border-surface-border bg-surface-raised p-5 transition-colors hover:border-accent/40"
          >
            <h2 className="font-medium text-white">Messages</h2>
            <p className="mt-1 text-sm text-slate-400">Raw pipeline input</p>
          </Link>
        </li>
      </ul>
    </div>
  );
}

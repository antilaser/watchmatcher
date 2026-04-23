import Link from "next/link";

const links = [
  { href: "/", label: "Home" },
  { href: "/matches", label: "Matches" },
  { href: "/alerts", label: "Alerts" },
  { href: "/messages", label: "Messages" },
];

export function Nav() {
  return (
    <header className="border-b border-surface-border bg-surface-raised/80 backdrop-blur-sm sticky top-0 z-10">
      <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-4 py-3">
        <Link href="/" className="font-semibold tracking-tight text-accent">
          watchmatch
        </Link>
        <nav className="flex flex-wrap gap-1 text-sm">
          {links.map(({ href, label }) => (
            <Link
              key={href}
              href={href}
              className="rounded-md px-3 py-1.5 text-slate-300 hover:bg-surface-border hover:text-white transition-colors"
            >
              {label}
            </Link>
          ))}
        </nav>
      </div>
    </header>
  );
}

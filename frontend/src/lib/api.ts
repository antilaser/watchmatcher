function normalizeBase(url: string): string {
  return url.replace(/\/$/, "");
}

/** Base URL for `/matches`, `/alerts`, etc. (includes `/api/v1`). */
export function getApiBase(): string {
  const env = process.env.NEXT_PUBLIC_API_BASE_URL?.trim();
  if (env) return normalizeBase(env);
  if (typeof window !== "undefined") {
    return `${window.location.origin}/api/v1`;
  }
  // Build-time / Node (no browser): same-origin prod does not need this path at runtime.
  return "http://127.0.0.1:8000/api/v1";
}

export async function apiFetch<T>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  const base = getApiBase();
  const url = `${base}${path.startsWith("/") ? path : `/${path}`}`;
  const res = await fetch(url, {
    ...init,
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
      ...init?.headers,
    },
  });
  const text = await res.text();
  if (!res.ok) {
    throw new Error(text || `${res.status} ${res.statusText}`);
  }
  if (res.status === 204 || !text.trim()) return undefined as T;
  return JSON.parse(text) as T;
}

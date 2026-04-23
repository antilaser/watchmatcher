export function alertSummary(payload: Record<string, unknown>): string {
  const s = payload.summary;
  if (typeof s === "string" && s.trim()) return s;
  const title = payload.title;
  if (typeof title === "string" && title.trim()) return title;
  const body = payload.body;
  if (typeof body === "string" && body.trim()) return body.slice(0, 2000);
  try {
    return JSON.stringify(payload, null, 0).slice(0, 2000);
  } catch {
    return String(payload);
  }
}

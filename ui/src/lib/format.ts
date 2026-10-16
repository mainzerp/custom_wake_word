/** "45s", "12m 5s", "1h 20m"; "–" when unknown. */
export function duration(s: number | null | undefined): string {
  if (s == null || !Number.isFinite(s)) return "–";
  s = Math.max(0, Math.round(s));
  if (s >= 3600) return `${Math.floor(s / 3600)}h ${Math.round((s % 3600) / 60)}m`;
  if (s >= 60) return `${Math.floor(s / 60)}m ${s % 60}s`;
  return `${s}s`;
}

/** Wall-clock time `s` seconds from now, e.g. "14:32" (with the weekday when it is not today). */
export function finishAt(s: number | null | undefined): string {
  if (s == null || !Number.isFinite(s)) return "–";
  const at = new Date(Date.now() + s * 1000);
  const time = at.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });
  return at.toDateString() === new Date().toDateString() ? time : `${at.toLocaleDateString(undefined, { weekday: "short" })} ${time}`;
}

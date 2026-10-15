import type { Clip, Session } from "./types";

export function formatSession(name: string): string {
  return `${name.slice(0, 4)}-${name.slice(4, 6)}-${name.slice(6, 8)} ${name.slice(9, 11)}:${name.slice(11, 13)}`;
}

export function labelCounts(s: Session) {
  const counts = { unsorted: 0, positive: 0, negative: 0 };
  for (const c of s.clips) counts[c.label ?? "unsorted"]++;
  return counts;
}

/** Clip bounds within the full recording; older sessions only stored the word span. */
export function clipBounds(c: Clip, pad = 0.15): [number, number] {
  return [c.clip_start ?? Math.max(0, c.start - pad), c.clip_end ?? c.start + c.length + pad];
}

export const clipIndex = (c: Clip) => c.name.slice(-7, -4);

import type { Counts } from "./types";

export const counts = $state<Counts>({ positive: 0, negative: 0 });

export function setCounts(c: Counts) {
  counts.positive = c.positive;
  counts.negative = c.negative;
}

export type Toast = { id: number; text: string; kind: "info" | "error" };
export const toasts = $state<Toast[]>([]);
let nextId = 1;

export function toast(text: string, kind: Toast["kind"] = "info") {
  const id = nextId++;
  toasts.push({ id, text, kind });
  setTimeout(() => {
    const i = toasts.findIndex((t) => t.id === id);
    if (i >= 0) toasts.splice(i, 1);
  }, kind === "error" ? 6000 : 3200);
}

export function toastError(e: unknown) {
  toast(e instanceof Error ? e.message : String(e), "error");
}

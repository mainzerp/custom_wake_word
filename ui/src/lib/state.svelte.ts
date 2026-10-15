import type { Counts, Project } from "./types";

export const app = $state<{ project: Project | null }>({ project: null });

export function setProject(p: Project | null) {
  app.project = p;
}

export function setCounts(c: Counts) {
  if (!app.project) return;
  app.project.summary.positive = c.positive;
  app.project.summary.negative = c.negative;
}

export function slug(): string {
  if (!app.project) throw new Error("no project selected");
  return app.project.slug;
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

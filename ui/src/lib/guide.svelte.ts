import { projects } from "./api";
import { i18n, t } from "./i18n.svelte";
import type { Guide, GuideChange } from "./types";

/** The project's "what next" guidance (trainer/guide.py), refreshed while a project page is open. */
export const guide = $state<{ slug: string | null; data: Guide | null }>({ slug: null, data: null });

export async function refreshGuide(slug: string) {
  try {
    const data = await projects.guide(slug);
    if (guide.slug !== slug) guide.slug = slug;
    guide.data = data;
  } catch {
    // the guide is a hint; a failed poll keeps the last one
  }
}


/** "+234 mined false triggers" in the UI language (the server sends the English version as a param). */
export function describeChanges(changes: GuideChange[]): string {
  return changes
    .map((c) => {
      const d = c.now - c.before;
      const label = t(c.label);
      return `${d > 0 ? "+" : ""}${d.toLocaleString(i18n.lang === "de" ? "de-DE" : "en-US")} ${i18n.lang === "de" ? label : label.toLowerCase()}`;
    })
    .join(", ");
}

/** Title and text of the guide's recommendation, translated from its templates. */
export function nextText(next: Guide["next"]): { title: string; text: string } {
  const params = { ...next.params, ...(next.params.changes != null && guide.data ? { changes: describeChanges(guide.data.changes) } : {}) };
  return { title: t(next.tpl.title, params), text: t(next.tpl.text, params) };
}

export function noteText(note: Guide["steps"][string]): string {
  return t(note.tpl, note.params);
}

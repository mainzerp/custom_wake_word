/**
 * UI language (English / German). Strings are written in English and wrapped in t(); the English text is the key, so
 * a missing translation falls back to it. German lives in ./i18n/de/*.ts (one partial per area, merged in index.ts).
 *
 *   t("Generate {n} clips", { n: 20000 })   placeholders {name}; numbers are formatted for the UI language
 *   plural(n, "{n} model", "{n} models")   picks by n, then t()
 *
 * `npm run i18n` lists t() keys without a German entry.
 */
import de from "./i18n/de";

export type Lang = "en" | "de";
export const LANGS: { id: Lang; label: string }[] = [
  { id: "en", label: "English" },
  { id: "de", label: "Deutsch" },
];
const STORE = "wakeforge.lang";
const DICTS: Record<Lang, Record<string, string>> = { en: {}, de };

function initial(): Lang {
  try {
    const saved = localStorage.getItem(STORE);
    if (saved === "en" || saved === "de") return saved;
  } catch {
    // private mode: fall through to the browser language
  }
  return navigator.language?.toLowerCase().startsWith("de") ? "de" : "en";
}

export const i18n = $state<{ lang: Lang }>({ lang: initial() });
document.documentElement.lang = i18n.lang;

export function setLang(lang: Lang) {
  i18n.lang = lang;
  document.documentElement.lang = lang;
  try {
    localStorage.setItem(STORE, lang);
  } catch {
    // the choice then lasts for this tab only
  }
}

/** Locale for toLocaleString & co. */
export const locale = () => (i18n.lang === "de" ? "de-DE" : "en-US");

export function t(text: string, params?: Record<string, string | number | null | undefined>): string {
  const s = DICTS[i18n.lang][text] ?? text;
  if (!params) return s;
  return s.replace(/\{(\w+)\}/g, (m, k: string) => {
    const v = params[k];
    return v == null ? m : typeof v === "number" ? v.toLocaleString(locale()) : v;
  });
}

export function plural(n: number, one: string, many: string, params?: Record<string, string | number>): string {
  return t(n === 1 ? one : many, { n, ...params });
}

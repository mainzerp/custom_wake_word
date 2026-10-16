import { isStep, type StepId } from "./steps";

export type Route = { view: "home" } | { view: "new" } | { view: "setup" } | { view: "project"; slug: string; step: StepId | null };

function parse(): Route {
  const [head, slug, step] = location.hash.replace(/^#\/?/, "").split("/");
  if (head === "new") return { view: "new" };
  if (head === "setup") return { view: "setup" };
  if (head === "p" && slug) return { view: "project", slug: decodeURIComponent(slug), step: isStep(step) ? step : null };
  return { view: "home" };
}

export const router = $state<{ route: Route }>({ route: parse() });
addEventListener("hashchange", () => (router.route = parse()));

export const href = {
  home: "#/",
  new: "#/new",
  setup: "#/setup",
  project: (slug: string, step?: StepId) => `#/p/${encodeURIComponent(slug)}${step ? `/${step}` : ""}`,
};

export const go = (hash: string) => (location.hash = hash);

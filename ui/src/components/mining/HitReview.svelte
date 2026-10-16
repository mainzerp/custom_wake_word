<script lang="ts">
  import { untrack } from "svelte";
  import HitCard from "./HitCard.svelte";
  import { mining } from "../../lib/api";
  import { plural, t } from "../../lib/i18n.svelte";
  import { player } from "../../lib/player.svelte";
  import { toast, toastError } from "../../lib/state.svelte";
  import type { MiningHit, MiningLabel, MiningRun, MiningStatus } from "../../lib/types";

  let { run, onrun }: { run: MiningRun; onrun: (r: MiningRun, totals: MiningStatus["totals"]) => void } = $props();

  type Filter = "open" | "auto" | MiningLabel | "all";
  // $derived so the labels follow the UI language.
  const FILTERS: { id: Filter; label: string }[] = $derived([
    { id: "open", label: t("To check") },
    { id: "auto", label: t("Auto: not it") },
    { id: "negative", label: t("Not it") },
    { id: "positive", label: t("Wake word") },
    { id: "skip", label: t("Skipped") },
    { id: "all", label: t("All") },
  ]);

  let hits = $state<MiningHit[]>([]);
  let filter = $state<Filter>("open");
  let focus = $state<number | null>(null);
  let autoplay = $state(true);
  let busy = $state(false);

  // Most suspicious first: what sounds or reads closest to the wake word, then the model's score.
  const suspicion = (h: MiningHit) => (h.match ? -1 : Math.min(h.check?.contained ?? 1, h.check?.text_distance ?? 1));
  const shown = $derived(
    hits
      .filter((h) => filter === "all" || (filter === "open" ? !h.label : filter === "auto" ? h.auto : h.label === filter))
      .sort((a, b) => (filter === "open" ? suspicion(a) - suspicion(b) : 0) || b.score - a.score),
  );
  const count = (f: Filter) => (f === "all" ? hits.length : run.counts[f]);
  const focusIndex = $derived(shown.findIndex((h) => h.n === focus));
  // Bulk labeling only takes what nothing speaks against: not flagged by the check, wake word not in the transcript.
  const openUnmatched = $derived(hits.filter((h) => !h.label && !h.match && h.check?.verdict !== "review"));
  const url = (h: MiningHit) => mining.clipUrl(run.id, h.n);

  $effect(() => {
    const id = run.id;
    untrack(async () => {
      try {
        const res = await mining.run(id);
        hits = res.hits;
        if (!res.hits.some((h) => !h.label)) filter = "all";
      } catch (e) {
        toastError(e);
      }
    });
  });

  function play(h: MiningHit) {
    player.play(url(h), url(h));
  }

  function select(h: MiningHit | undefined) {
    focus = h?.n ?? null;
    if (h && autoplay) play(h);
    else if (!h) player.stop();
  }

  function step(d: number) {
    if (!shown.length) return;
    const i = focusIndex < 0 ? 0 : Math.max(0, Math.min(shown.length - 1, focusIndex + d));
    select(shown[i]);
  }

  async function label(ns: number[], value: MiningLabel | null) {
    busy = true;
    try {
      const i = focusIndex;
      const res = await mining.label(run.id, ns, value);
      const set = new Set(ns);
      hits = hits.map((h) => (set.has(h.n) ? { ...h, label: value, auto: false } : h));
      onrun(res.run, res.totals);
      // In a filtered view the labeled clip leaves the list: move on to the one that took its place.
      if (ns.length === 1 && ns[0] === focus && !shown.some((h) => h.n === focus)) select(shown[Math.min(i, shown.length - 1)]);
      else if (ns.length === 1 && ns[0] === focus && filter === "all") step(1);
    } catch (e) {
      toastError(e);
    } finally {
      busy = false;
    }
  }

  async function bulk() {
    const ns = openUnmatched.map((h) => h.n);
    const kept = hits.filter((h) => !h.label).length - ns.length;
    const stay = kept
      ? ` ${plural(kept, "{n} that the check flagged or whose transcript names the wake word stays open.", "{n} that the check flagged or whose transcript names the wake word stay open.")}`
      : "";
    if (!confirm(plural(ns.length, "Label {n} open trigger as \"not the wake word\"?", "Label {n} open triggers as \"not the wake word\"?") + stay)) return;
    await label(ns, "negative");
    toast(plural(ns.length, "{n} false trigger added to training.", "{n} false triggers added to training."));
  }

  async function onkey(e: KeyboardEvent) {
    if (e.ctrlKey || e.metaKey || e.altKey || /^(INPUT|SELECT|TEXTAREA)$/.test((e.target as HTMLElement).tagName)) return;
    const h = shown[focusIndex];
    const actions: Record<string, () => unknown> = {
      arrowright: () => step(1),
      j: () => step(1),
      arrowleft: () => step(-1),
      k: () => step(-1),
      escape: () => player.stop(),
      ...(h && {
        n: () => label([h.n], h.label === "negative" ? null : "negative"),
        p: () => label([h.n], h.label === "positive" ? null : "positive"),
        x: () => label([h.n], h.label === "skip" ? null : "skip"),
        u: () => label([h.n], null),
        r: () => play(h),
        " ": () => play(h),
      }),
    };
    const action = actions[e.key.toLowerCase()];
    if (!action) return;
    e.preventDefault();
    if (busy) return;
    await action();
  }
</script>

<svelte:window onkeydown={onkey} />

<section class="panel review">
  <div class="head">
    <div>
      <span class="eyebrow">{t("Review")}</span>
      <p class="dim sub">
        {#if run.triaged}
          {plural(run.counts.auto, "The automatic check labeled {n} clear false trigger.", "The automatic check labeled {n} clear false triggers.")}
          {t("What it flagged waits under")} <strong>{t("To check")}</strong>{t(", most suspicious first.")}
          {t("If you like, spot-check")} <strong>{t("Auto: not it")}</strong>{t(": your label always wins.")}
        {:else}
          {t("Listen to every trigger, or let")} <strong>{t("Check automatically")}</strong> {t("in the scan list do most of it.")}
        {/if}
        <strong>{t("Not it")}</strong> {t("becomes a negative for the next training run,")} <strong>{t("Wake word")}</strong>
        {t("a positive (someone really said it).")} {t("The magenta band is the part that goes into training.")}
        {t("Keys: J/K or ←/→ move, Space plays, N / P / X label, U clears.")}
      </p>
    </div>
    <div class="tools">
      <label class="check"><input type="checkbox" bind:checked={autoplay} /> {t("Auto-play")}</label>
      <button class="small" onclick={bulk} disabled={busy || !openUnmatched.length}>{t("All open → not it ({n})", { n: openUnmatched.length })}</button>
    </div>
  </div>

  <div class="filters">
    {#each FILTERS as f (f.id)}
      <button class="small" class:sel={filter === f.id} onclick={() => ((filter = f.id), (focus = null))}>
        {f.label} <span class="mono faint">{count(f.id)}</span>
      </button>
    {/each}
    {#if run.matches}
      <span class="faint small-note">{t("{n} with the wake word in the transcript (dashed)", { n: run.matches })}</span>
    {/if}
  </div>

  {#if shown.length}
    <div class="grid">
      {#each shown as h (h.n)}
        <HitCard hit={h} url={url(h)} focused={focus === h.n} device={run.cutoff} onfocus={() => select(h)} onlabel={(l) => label([h.n], l)} />
      {/each}
    </div>
  {:else}
    <p class="dim">{filter === "open" ? t("Everything reviewed.") : t("Nothing here.")}</p>
  {/if}
</section>

<style>
  .review {
    padding: 20px 22px;
    display: flex;
    flex-direction: column;
    gap: 14px;
  }
  .head {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 16px;
    flex-wrap: wrap;
  }
  .sub {
    margin: 6px 0 0;
    font-size: 13px;
    line-height: 1.55;
    max-width: 760px;
  }
  .sub strong {
    color: var(--text);
    font-weight: 600;
  }
  .tools {
    display: flex;
    align-items: center;
    gap: 14px;
  }
  .check {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 13px;
    cursor: pointer;
  }
  .check input {
    accent-color: var(--cyan);
  }
  .filters {
    display: flex;
    gap: 6px;
    flex-wrap: wrap;
    align-items: center;
  }
  .sel {
    border-color: var(--cyan);
    color: var(--cyan);
    background: rgba(41, 240, 255, 0.1);
  }
  .small-note {
    font-size: 12.5px;
    margin-left: 8px;
  }
  .grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
    gap: 10px;
  }
</style>

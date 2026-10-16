<script lang="ts">
  import { untrack } from "svelte";
  import Icon from "../Icon.svelte";
  import { tts } from "../../lib/api";
  import { t } from "../../lib/i18n.svelte";
  import { toastError } from "../../lib/state.svelte";
  import type { SoundAlike } from "../../lib/types";

  let {
    words = $bindable(),
    language,
    phrases,
  }: { words: string[]; language: string; phrases: string[] } = $props();

  let draft = $state("");
  let busy = $state(false);
  let scores = $state<Record<string, SoundAlike>>({});
  let suggestions = $state<SoundAlike[]>([]);

  const valid = $derived(phrases.map((p) => p.trim()).filter(Boolean));
  const key = $derived(JSON.stringify([language, valid]));
  const conflicts = $derived(words.filter((w) => scores[w]?.level === "conflict"));

  async function rescore(list: string[]) {
    if (!valid.length || !list.length) return;
    try {
      const res = await tts.soundAlikes(language, valid, list);
      for (const s of res.words) scores[s.text] = s;
    } catch (e) {
      toastError(e);
    }
  }

  // Spellings or language changed: all distances are stale.
  $effect(() => {
    void key;
    untrack(() => {
      scores = {};
      suggestions = [];
      rescore([...words]);
    });
  });

  async function suggest() {
    busy = true;
    try {
      const res = await tts.soundAlikes(language, valid, [...words], 24);
      suggestions = res.suggestions;
      if (!suggestions.length) toastError(t("No further sound-alikes found."));
    } catch (e) {
      toastError(e);
    } finally {
      busy = false;
    }
  }

  function add(list: string[]) {
    const fresh = list.map((w) => w.trim()).filter((w) => w && !words.includes(w));
    if (!fresh.length) return;
    words.push(...fresh);
    for (const s of suggestions) if (fresh.includes(s.text)) scores[s.text] = s;
    suggestions = suggestions.filter((s) => !fresh.includes(s.text));
    const unknown = fresh.filter((w) => !scores[w]);
    if (unknown.length) rescore(unknown);
  }

  function addDraft() {
    add(draft.split(",")); // "Davis, Marvin" adds both
    draft = "";
  }

  const fmt = (s?: SoundAlike) => (s ? s.distance.toFixed(2) : "…");
</script>

<div class="alikes">
  <div class="head">
    <div>
      <span class="eyebrow">{t("Sound-alikes")} <span class="faint">{t("(negatives)")}</span></span>
      <p class="dim small">
        {t("Words that sound close to the wake word but are not it, e.g.")} <span class="mono">Davis</span> {t("or")}
        <span class="mono">Marvin</span>. {t("The synthetic step speaks them with all voices, so the model learns to tell them apart. Δ is the phone distance to the closest spelling: up to 0.35 they count as the wake word itself and are refused, 0.35–0.65 are the useful hard negatives.")}
      </p>
    </div>
    <button class="small" onclick={suggest} disabled={busy || !valid.length}>
      <Icon name="sparkles" size={14} />
      {busy ? t("Searching…") : t("Suggest")}
    </button>
  </div>

  {#if words.length}
    <ul class="chips">
      {#each words as w, i (w)}
        {@const s = scores[w]}
        <li class="word {s?.level ?? ''}" title={s?.level === "conflict" ? t("Sounds like the wake word itself") : s?.level === "far" ? t("Far away: generic speech covers it already") : ""}>
          <span>{w}</span>
          <span class="mono d">Δ {fmt(s)}</span>
          <button class="ghost x" onclick={() => words.splice(i, 1)} aria-label={t("Remove {word}", { word: w })}><Icon name="x" size={12} /></button>
        </li>
      {/each}
    </ul>
  {:else}
    <p class="faint small">{t("None yet. Hit Suggest, or type your own below.")}</p>
  {/if}
  {#if conflicts.length}
    <p class="hint err">{t("Remove {words}: too close to the wake word, saving is refused.", { words: conflicts.join(", ") })}</p>
  {/if}

  {#if suggestions.length}
    <div class="suggest">
      <div class="suggest-head">
        <span class="label">{t("Suggestions")} <span class="faint">{t("(click to add)")}</span></span>
        <button class="ghost small" onclick={() => add(suggestions.map((s) => s.text))}><Icon name="plus" size={14} /> {t("Add all")}</button>
      </div>
      <ul class="chips">
        {#each suggestions as s (s.text)}
          <li>
            <button class="word sug" onclick={() => add([s.text])} title={s.kind === "word" ? t("Real word from the voice bank") : t("Letter edit ({kind})", { kind: t(s.kind ?? "") })}>
              <Icon name="plus" size={12} />
              <span>{s.text}</span>
              <span class="mono d">Δ {fmt(s)}</span>
            </button>
          </li>
        {/each}
      </ul>
    </div>
  {/if}

  <form class="add" onsubmit={(e) => (e.preventDefault(), addDraft())}>
    <input bind:value={draft} maxlength="200" placeholder={t("Add sound-alikes (comma separated)")} />
    <button type="submit" class="small" disabled={!draft.trim()}><Icon name="plus" size={14} /> {t("Add")}</button>
  </form>
</div>

<style>
  .alikes {
    display: flex;
    flex-direction: column;
    gap: 10px;
  }
  .head,
  .suggest-head {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 16px;
  }
  .suggest-head {
    align-items: center;
  }
  .head button,
  .suggest-head button,
  .add button {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    flex: none;
  }
  .small {
    font-size: 13px;
    line-height: 1.5;
    margin: 6px 0 0;
  }
  .label {
    font-size: 12.5px;
    color: var(--text-dim);
  }
  .chips {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
  }
  .word {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 3px 4px 3px 10px;
    border-radius: 999px;
    border: 1px solid rgba(255, 61, 242, 0.4);
    background: rgba(255, 61, 242, 0.06);
    font-size: 13px;
  }
  .word.conflict {
    border-color: var(--danger);
    background: rgba(255, 79, 123, 0.14);
  }
  .word.far {
    border-color: var(--line-strong);
    background: none;
    color: var(--text-dim);
  }
  .word .d {
    font-size: 11px;
    color: var(--text-dim);
  }
  .word.conflict .d {
    color: var(--danger);
  }
  .x {
    padding: 2px;
    border: none;
    border-radius: 50%;
    display: inline-flex;
  }
  .sug {
    padding: 3px 10px 3px 8px;
    border-style: dashed;
    border-color: var(--line-strong);
    background: none;
    cursor: pointer;
  }
  .sug:hover {
    border-color: var(--magenta);
    background: rgba(255, 61, 242, 0.08);
  }
  .suggest {
    display: flex;
    flex-direction: column;
    gap: 8px;
    padding: 12px;
    border: 1px dashed var(--line);
    border-radius: var(--radius-sm);
  }
  .hint {
    margin: 0;
    font-size: 12.5px;
  }
  .hint.err {
    color: var(--danger);
  }
  .add {
    display: flex;
    gap: 8px;
  }
  .add input {
    flex: 1;
  }
</style>

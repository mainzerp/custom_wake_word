<script lang="ts">
  import { untrack } from "svelte";
  import Icon from "../Icon.svelte";
  import { tts } from "../../lib/api";
  import { t } from "../../lib/i18n.svelte";
  import { toast, toastError } from "../../lib/state.svelte";
  import type { SoundAlike } from "../../lib/types";

  let {
    words = $bindable(),
    language,
    phrases,
    project,
    auto = "off",
  }: {
    words: string[];
    language: string;
    phrases: string[];
    /** slug: suggestions also include words from this project's mined false triggers */
    project?: string;
    /** while the list is empty: "show" fetches suggestions by itself, "add" also takes them all (the wizard) */
    auto?: "off" | "show" | "add";
  } = $props();

  let draft = $state("");
  let busy = $state(false);
  let scores = $state<Record<string, SoundAlike>>({});
  let suggestions = $state<SoundAlike[]>([]);

  const valid = $derived(phrases.map((p) => p.trim()).filter(Boolean));
  const key = $derived(JSON.stringify([language, valid]));
  const conflicts = $derived(words.filter((w) => scores[w]?.level === "conflict"));
  // The spellings the list was made for: when they change, the list may no longer fit them (recreate offers new ones).
  let basis = $state(untrack(() => key));
  const stale = $derived(words.length > 0 && key !== basis);
  // In the wizard the list is ours until the user touches it: then follow the spellings without asking.
  let autoList: string[] | null = null;

  async function rescore(list: string[]) {
    if (!valid.length || !list.length) return;
    try {
      const res = await tts.soundAlikes(language, valid, list);
      for (const s of res.words) scores[s.text] = s;
    } catch (e) {
      toastError(e);
    }
  }

  // Spellings or language changed: all distances are stale. With auto, an empty list gets suggestions by itself
  // (debounced, the spellings may still be typed).
  let autoDone = false;
  $effect(() => {
    void key;
    untrack(() => {
      scores = {};
      suggestions = [];
      rescore([...words]);
    });
    if (auto === "off") return;
    const id = setTimeout(() => untrack(() => {
      if (!valid.length) return;
      if (!autoDone && !words.length) {
        autoDone = true;
        suggest(true);
      } else if (auto === "add" && autoList && JSON.stringify(autoList) === JSON.stringify(words) && key !== basis) {
        recreate(true);
      }
    }), 700);
    return () => clearTimeout(id);
  });

  /** Replace the list with fresh suggestions for the current spellings. */
  async function recreate(silent = false) {
    if (!silent && words.length && !confirm(t("Replace the {n} sound-alikes with new suggestions for the current spellings? Words you typed yourself are replaced too.", { n: words.length }))) return;
    busy = true;
    try {
      const res = await tts.soundAlikes(language, valid, [], 24, project);
      words.splice(0, words.length, ...res.suggestions.map((x) => x.text));
      scores = Object.fromEntries(res.suggestions.map((x) => [x.text, x]));
      suggestions = [];
      basis = key;
      if (auto === "add") autoList = [...words];
      if (!silent) toast(t("{n} sound-alikes for the current spellings. Generate their clips in step 2.", { n: words.length }));
    } catch (e) {
      toastError(e);
    } finally {
      busy = false;
    }
  }

  async function suggest(automatic = false) {
    busy = true;
    try {
      const res = await tts.soundAlikes(language, valid, [...words], 24, project);
      suggestions = res.suggestions;
      if (automatic && auto === "add" && !words.length) {
        add(suggestions.map((s) => s.text));
        basis = key;
        autoList = [...words];
      }
      else if (!suggestions.length && !automatic) toastError(t("No further sound-alikes found."));
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
    <div class="buttons">
      <button class="small" onclick={() => suggest()} disabled={busy || !valid.length}>
        <Icon name="sparkles" size={14} />
        {busy ? t("Searching…") : t("Suggest")}
      </button>
      {#if words.length}
        <button class="small" class:warn={stale} onclick={() => recreate()} disabled={busy || !valid.length}
          title={t("Replace the list with new suggestions for the current spellings")}>
          <Icon name="replay" size={14} /> {t("Recreate")}
        </button>
      {/if}
    </div>
  </div>

  {#if stale}
    <div class="stale">
      <span>{t("The TTS spellings changed since this list was made. Recreate it for the new spellings, or keep it (the distances below are already updated).")}</span>
      <span class="stale-actions">
        <button class="small warn" onclick={() => recreate()} disabled={busy}><Icon name="replay" size={14} /> {t("Recreate")}</button>
        <button class="ghost small" onclick={() => (basis = key)}>{t("Keep list")}</button>
      </span>
    </div>
  {/if}

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
  {:else if busy}
    <p class="faint small">{t("Looking for sound-alikes…")}</p>
  {:else}
    <p class="faint small">{t("None yet. Hit Suggest, or type your own below.")}</p>
  {/if}
  {#if auto === "add" && words.length}
    <p class="faint small">{t("Suggested for you: remove what you do not want (×). The sound-alike clips are generated in step 2.")}</p>
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
            <button class="word sug" class:mined={s.kind === "mined"} onclick={() => add([s.text])}
              title={s.kind === "mined" ? t("Heard in a real false trigger while mining") : s.kind === "word" ? t("Real word from the voice bank") : t("Letter edit ({kind})", { kind: t(s.kind ?? "") })}>
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
  .word.sug.mined {
    border-color: rgba(255, 190, 70, 0.55);
  }
  .buttons {
    display: flex;
    gap: 6px;
    flex: none;
  }
  .buttons button,
  .stale button {
    display: inline-flex;
    align-items: center;
    gap: 6px;
  }
  button.warn {
    border-color: var(--amber);
    color: var(--amber);
  }
  .stale {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 14px;
    padding: 10px 12px;
    border-radius: var(--radius-sm);
    border: 1px solid rgba(255, 190, 70, 0.45);
    background: rgba(255, 190, 70, 0.07);
    font-size: 13px;
    line-height: 1.5;
  }
  .stale-actions {
    display: flex;
    gap: 6px;
    flex: none;
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

<script lang="ts">
  import Icon from "../Icon.svelte";
  import { LANGUAGES, type ProjectSettings } from "../../lib/types";

  type Section = "name" | "phrases" | "manifest";

  let {
    settings = $bindable(),
    sections = ["name", "phrases", "manifest"],
    hero = false,
  }: { settings: ProjectSettings; sections?: Section[]; hero?: boolean } = $props();

  let draft = $state("");

  const syllables = $derived((settings.wake_word.match(/[aeiouyäöü]+/gi) ?? []).length);
  const hint = $derived.by(() => {
    const word = settings.wake_word.trim();
    if (!word) return null;
    if (syllables < 2) return { kind: "warn", text: "Very short. One-syllable words trigger on everyday speech." };
    if (syllables > 5) return { kind: "warn", text: "Long phrases are harder to say consistently." };
    return { kind: "pos", text: `~${syllables} syllables, a good length.` };
  });

  function addPhrase() {
    const p = draft.trim();
    if (p && !settings.tts_phrases.includes(p)) settings.tts_phrases.push(p);
    draft = "";
  }
</script>

{#if sections.includes("name")}
  <div class="name" class:hero>
    <label class="field">
      Wake word
      <input class="word" bind:value={settings.wake_word} maxlength="40" placeholder="e.g. Hey Nova" autocomplete="off" />
    </label>
    <label class="field lang">
      Language
      <select bind:value={settings.language}>
        {#each Object.entries(LANGUAGES) as [code, name] (code)}
          <option value={code}>{name} ({code})</option>
        {/each}
      </select>
    </label>
  </div>
  {#if hint}
    <p class="hint {hint.kind}"><span class="dot"></span>{hint.text}</p>
  {/if}
{/if}

{#if sections.includes("phrases")}
  <div class="phrases">
    <span class="eyebrow">TTS spellings</span>
    <p class="dim small">
      The TTS voices read text literally. Add spellings that make them sound like you, e.g. <span class="mono">Dscharwis</span> for
      "Jarvis" in German. Every spelling is spread across all speakers.
    </p>
    <ul>
      {#each settings.tts_phrases as _, i (i)}
        <li>
          <input bind:value={settings.tts_phrases[i]} maxlength="60" aria-label="Spelling {i + 1}" />
          <button class="ghost small" onclick={() => settings.tts_phrases.splice(i, 1)} aria-label="Remove spelling" disabled={settings.tts_phrases.length < 2}>
            <Icon name="x" size={14} />
          </button>
        </li>
      {/each}
    </ul>
    <form class="add" onsubmit={(e) => (e.preventDefault(), addPhrase())}>
      <input bind:value={draft} maxlength="60" placeholder="Add a spelling" />
      <button type="submit" class="small" disabled={!draft.trim()}><Icon name="plus" size={14} /> Add</button>
    </form>
  </div>
{/if}

{#if sections.includes("manifest")}
  <div class="manifest">
    <span class="eyebrow">ESPHome manifest</span>
    <div class="row">
      <label class="field">
        Author
        <input bind:value={settings.author} maxlength="60" placeholder="optional" />
      </label>
      <label class="field">
        Website
        <input bind:value={settings.website} maxlength="200" placeholder="https://… (optional)" />
      </label>
    </div>
  </div>
{/if}

<style>
  .name {
    display: grid;
    grid-template-columns: 1fr 220px;
    gap: 14px;
    align-items: end;
  }
  .field input,
  .field select {
    font-size: 15px;
  }
  .hero .word {
    font-family: var(--font-display);
    font-size: 30px;
    padding: 14px 16px;
    letter-spacing: 0.02em;
  }
  .hero {
    align-items: stretch;
  }
  .hero .lang select {
    flex: 1;
    font-size: 16px;
  }
  .hint {
    display: flex;
    align-items: center;
    gap: 8px;
    margin: 12px 0 0;
    font-size: 13px;
  }
  .hint.pos {
    color: var(--cyan);
  }
  .hint.warn {
    color: var(--amber);
  }
  .phrases,
  .manifest {
    display: flex;
    flex-direction: column;
    gap: 10px;
  }
  .small {
    font-size: 13px;
    line-height: 1.5;
    margin: 0;
  }
  ul {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  li,
  .add {
    display: flex;
    gap: 8px;
  }
  li input,
  .add input {
    flex: 1;
  }
  .add button {
    display: inline-flex;
    align-items: center;
    gap: 4px;
  }
  .row {
    display: grid;
    grid-template-columns: 1fr 1.6fr;
    gap: 12px;
  }
  @media (max-width: 700px) {
    .name,
    .row {
      grid-template-columns: 1fr;
    }
  }
</style>

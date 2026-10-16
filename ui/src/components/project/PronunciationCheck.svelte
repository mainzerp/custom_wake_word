<script lang="ts">
  import Icon from "../Icon.svelte";
  import MiniClip from "../MiniClip.svelte";
  import { tts } from "../../lib/api";
  import { t } from "../../lib/i18n.svelte";
  import { toastError } from "../../lib/state.svelte";
  import type { GenClip } from "../../lib/types";

  let { language, phrases }: { language: string; phrases: string[] } = $props();

  let busy = $state(false);
  let clips = $state<GenClip[]>([]);
  let checked = $state<string[]>([]);

  const valid = $derived(phrases.map((p) => p.trim()).filter(Boolean));
  const stale = $derived(clips.length > 0 && JSON.stringify(valid) !== JSON.stringify(checked));
  const groups = $derived(checked.map((p) => ({ phrase: p, clips: clips.filter((c) => c.phrase === p) })));

  async function check() {
    busy = true;
    try {
      const phrases = [...valid];
      const res = await tts.preview(language, phrases, 2);
      const t = Date.now();
      clips = res.clips.map((c) => ({ ...c, url: `${c.url}?t=${t}` }));
      checked = phrases;
    } catch (e) {
      toastError(e);
    } finally {
      busy = false;
    }
  }

  const voice = (v: string) => v.replace(/^(bank|design):/, "");
</script>

<div class="check">
  <div class="head">
    <div>
      <span class="eyebrow">{t("Pronunciation check")}</span>
      <p class="dim small">
        {t("One male and one female cloned voice per spelling, with the recognized phones (IPA) and their distance Δ to the closest spelling (≤ 0.30 is kept). Pink = this clip would be dropped. Takes about 40 s.")}
      </p>
    </div>
    <button class="small" onclick={check} disabled={busy || !valid.length}>
      <Icon name={busy ? "replay" : "play"} size={14} />
      {busy ? t("Synthesizing…") : clips.length ? t("New voices") : t("Check pronunciation")}
    </button>
  </div>
  {#if stale}
    <p class="hint warn">{t("Spellings changed since this check.")}</p>
  {/if}
  {#each groups as g (g.phrase)}
    <div class="phrase">
      <div class="phrase-head">
        <strong>{g.phrase}</strong>
        {#if g.clips.some((c) => c.hit !== null && c.hit !== undefined)}
          {@const ok = g.clips.filter((c) => c.hit).length}
          <span class="chip {ok === g.clips.length ? 'pos' : ok ? 'warn' : 'neg'} mono">{t("{ok}/{total} recognized", { ok, total: g.clips.length })}</span>
        {/if}
      </div>
      <div class="grid">
        {#each g.clips as c (c.url)}
          <MiniClip url={c.url} label={voice(c.voice)} detail="Δ {c.distance?.toFixed(2) ?? '–'}" note={c.transcript} miss={c.hit === false} />
        {/each}
      </div>
    </div>
  {/each}
</div>

<style>
  .check {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }
  .head {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 16px;
  }
  .head button {
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
  .hint {
    margin: 0;
    font-size: 12.5px;
    color: var(--amber);
  }
  .phrase {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  .phrase-head {
    display: flex;
    align-items: center;
    gap: 12px;
  }
  .phrase-head strong {
    font-family: var(--font-display);
    font-weight: 600;
  }
  .grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(170px, 220px));
    gap: 10px;
  }
</style>

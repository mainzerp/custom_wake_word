<script lang="ts">
  import Icon from "../Icon.svelte";
  import Waveform from "../Waveform.svelte";
  import { t } from "../../lib/i18n.svelte";
  import { player } from "../../lib/player.svelte";
  import type { MiningHit, MiningLabel } from "../../lib/types";

  // The training cut around the trigger (trainer/mining/store.py CUT_BEFORE / CUT_AFTER).
  const CUT_BEFORE = 2.0;
  const CUT_AFTER = 0.3;

  let {
    hit,
    url,
    focused,
    device,
    onfocus,
    onlabel,
  }: {
    hit: MiningHit;
    url: string;
    focused: boolean;
    /** the model's own cutoff: triggers above it would fire on the device */
    device: number;
    onfocus: () => void;
    onlabel: (label: MiningLabel | null) => void;
  } = $props();

  let el: HTMLElement;
  const active = $derived(player.key === url);
  const regions = $derived([
    { id: "cut", start: Math.max(0, hit.pre - CUT_BEFORE), end: Math.min(hit.seconds, hit.pre + CUT_AFTER), color: "#ff3df2", active: focused },
  ]);

  $effect(() => {
    if (focused) el?.scrollIntoView({ block: "nearest", behavior: "smooth" });
  });

  function set(label: MiningLabel) {
    onlabel(hit.label === label ? null : label);
  }

  // The automatic check's reasons (trainer/mining/triage.py), several joined with "; "; unknown forms stay as they are.
  function reasonText(reason: string): string {
    return reason
      .split("; ")
      .map((r) => {
        let m: RegExpMatchArray | null;
        if (r === "transcript names the wake word") return t("transcript names the wake word");
        if (r === "the audio may contain the wake word") return t("the audio may contain the wake word");
        if ((m = r.match(/^text “(.*)” sounds like it \(([\d.]+)\)$/))) return t("text “{words}” sounds like it ({d})", { words: m[1], d: m[2] });
        if ((m = r.match(/^phones sound like it \(([\d.]+)\)$/))) return t("phones sound like it ({d})", { d: m[1] });
        if ((m = r.match(/^already labeled in scan (.+)$/))) return t("already labeled in scan {id}", { id: m[1] });
        return r;
      })
      .join("; ");
  }
</script>

<div
  class="hit"
  class:focused
  class:playing={active && player.playing}
  class:match={hit.match}
  data-label={hit.label}
  bind:this={el}
  role="button"
  tabindex="-1"
  onclick={onfocus}
  onkeydown={() => {}}
>
  <Waveform {url} height={46} buckets={90} {regions} progress={active && player.playing ? player.progress : null} />
  <div class="meta mono">
    <span class="score" class:dev={hit.score > device} title={t("Highest window average (raw peak {peak})", { peak: hit.peak.toFixed(3) })}>{hit.score.toFixed(3)}</span>
    {#if hit.match}<span class="chip pos" title={t("The transcript contains the wake word")}>{t("says it")}</span>{/if}
    {#if hit.auto}<span class="chip" title={t("Labeled by the automatic check")}>auto</span>{/if}
    <span class="faint ref" title={hit.ref}>{hit.ref} @ {hit.offset.toFixed(1)}s</span>
  </div>
  {#if hit.check && hit.check.verdict !== "negative" && hit.check.reason}<p class="reason">{reasonText(hit.check.reason)}</p>{/if}
  {#if hit.text}<p class="text">“{hit.text}”</p>{:else if hit.check?.asr}<p class="text" title={t("Whisper transcript")}>Whisper: “{hit.check.asr}”</p>{/if}
  {#if hit.check?.phones}<p class="phones mono" title={t("Recognized phones of the training cut (distance to the wake word {d})", { d: hit.check.contained.toFixed(2) })}>/{hit.check.phones}/</p>{/if}
  <div class="labels">
    <button class="small neg" class:on={hit.label === "negative"} onclick={(e) => { e.stopPropagation(); set("negative"); }} title={t("Not the wake word (N)")}>
      <Icon name="x" size={13} /> {t("Not it")}
    </button>
    <button class="small pos" class:on={hit.label === "positive"} onclick={(e) => { e.stopPropagation(); set("positive"); }} title={t("Really the wake word (P)")}>
      <Icon name="check" size={13} /> {t("Wake word")}
    </button>
    <button class="small ghost" class:on={hit.label === "skip"} onclick={(e) => { e.stopPropagation(); set("skip"); }} title={t("Unsure, leave out (X)")}>{t("Skip")}</button>
  </div>
</div>

<style>
  .hit {
    display: flex;
    flex-direction: column;
    gap: 8px;
    padding: 10px;
    border-radius: 12px;
    border: 1px solid var(--line);
    background: rgba(5, 4, 16, 0.4);
    cursor: pointer;
    min-width: 0;
    outline: none;
    transition: border-color 0.15s, box-shadow 0.15s;
  }
  .hit.focused {
    border-color: var(--violet);
    box-shadow: 0 0 0 1px var(--violet);
  }
  .hit.playing {
    border-color: var(--cyan);
    box-shadow: 0 0 22px -6px rgba(41, 240, 255, 0.7);
  }
  .hit.match {
    border-style: dashed;
  }
  .hit[data-label="negative"] {
    background: rgba(255, 61, 242, 0.06);
  }
  .hit[data-label="positive"] {
    background: rgba(41, 240, 255, 0.07);
  }
  .hit[data-label="skip"] {
    opacity: 0.6;
  }
  .meta {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 12px;
    min-width: 0;
  }
  .score {
    color: var(--text-dim);
  }
  .score.dev {
    color: var(--magenta);
  }
  .ref {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    min-width: 0;
  }
  .text {
    margin: 0;
    font-size: 12.5px;
    line-height: 1.45;
    color: var(--text-dim);
    display: -webkit-box;
    -webkit-line-clamp: 3;
    line-clamp: 3;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }
  .reason {
    margin: 0;
    font-size: 12px;
    color: var(--amber);
  }
  .phones {
    margin: 0;
    font-size: 11.5px;
    color: var(--text-faint, var(--text-dim));
    opacity: 0.8;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .labels {
    display: flex;
    gap: 6px;
    flex-wrap: wrap;
  }
  .labels button {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 4px 9px;
    font-size: 12px;
  }
  .labels .neg.on {
    border-color: var(--magenta);
    color: var(--magenta);
    background: rgba(255, 61, 242, 0.12);
  }
  .labels .pos.on {
    border-color: var(--cyan);
    color: var(--cyan);
    background: rgba(41, 240, 255, 0.12);
  }
  .labels .ghost.on {
    border-color: var(--line-strong);
    color: var(--text);
  }
</style>

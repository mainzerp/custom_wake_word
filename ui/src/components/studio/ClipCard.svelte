<script lang="ts">
  import Icon from "../Icon.svelte";
  import Waveform from "../Waveform.svelte";
  import { clipIndex } from "../../lib/session";
  import type { Clip, Label } from "../../lib/types";

  let {
    clip,
    url,
    focused,
    playing,
    progress,
    onplay,
    onlabel,
    ondelete,
  }: {
    clip: Clip;
    url: string;
    focused: boolean;
    playing: boolean;
    progress: number | null;
    onplay: () => void;
    onlabel: (label: Label) => void;
    ondelete: () => void;
  } = $props();

  let el: HTMLElement;
  $effect(() => {
    if (focused) el?.scrollIntoView({ block: "nearest", behavior: "smooth" });
  });

  const COLORS: Record<string, [string, string]> = {
    positive: ["#29f0ff", "#7af7ff"],
    negative: ["#ff3df2", "#ff8af6"],
    none: ["#9b6bff", "#29f0ff"],
  };
</script>

<article bind:this={el} class="clip {clip.label ?? ''}" class:focused class:playing>
  <button class="wave" onclick={onplay} aria-label="Play clip {clipIndex(clip)}">
    <Waveform {url} height={52} buckets={110} colors={COLORS[clip.label ?? "none"]} progress={playing ? progress : null} />
  </button>
  <div class="meta mono">
    <span class="idx">#{clipIndex(clip)}</span>
    <span>{clip.length.toFixed(2)}s</span>
    <span class:loud={clip.peak_db > -3} class:quiet={clip.peak_db < -30}>{clip.peak_db} dB</span>
  </div>
  <div class="actions">
    <button class="small pos" class:active={clip.label === "positive"} onclick={() => onlabel("positive")} title="Positive (P)">
      <Icon name="check" size={14} /> Pos
    </button>
    <button class="small neg" class:active={clip.label === "negative"} onclick={() => onlabel("negative")} title="Negative (N)">
      <Icon name="x" size={14} /> Neg
    </button>
    <button class="small danger icon" onclick={ondelete} title="Delete (D)" aria-label="Delete clip">
      <Icon name="trash" size={14} />
    </button>
  </div>
</article>

<style>
  .clip {
    display: flex;
    flex-direction: column;
    gap: 8px;
    padding: 10px;
    border-radius: 14px;
    border: 1px solid var(--line);
    background: rgba(5, 4, 16, 0.4);
    transition: border-color 0.15s, box-shadow 0.15s, transform 0.15s;
  }
  .clip.positive {
    border-color: rgba(41, 240, 255, 0.35);
    background: linear-gradient(180deg, rgba(41, 240, 255, 0.07), rgba(5, 4, 16, 0.4));
  }
  .clip.negative {
    border-color: rgba(255, 61, 242, 0.35);
    background: linear-gradient(180deg, rgba(255, 61, 242, 0.07), rgba(5, 4, 16, 0.4));
  }
  .clip.focused {
    border-color: #fff;
    box-shadow: 0 0 0 1px rgba(255, 255, 255, 0.4), 0 0 28px -4px rgba(155, 107, 255, 0.7);
    transform: translateY(-2px);
  }
  .wave {
    padding: 4px 2px;
    border: 0;
    background: transparent;
    border-radius: 8px;
  }
  .wave:hover:not(:disabled) {
    background: rgba(255, 255, 255, 0.03);
  }
  .meta {
    display: flex;
    justify-content: space-between;
    font-size: 11.5px;
    color: var(--text-faint);
  }
  .idx {
    color: var(--text-dim);
  }
  .loud {
    color: var(--danger);
  }
  .quiet {
    color: var(--amber);
  }
  .actions {
    display: grid;
    grid-template-columns: 1fr 1fr auto;
    gap: 6px;
  }
  .actions button {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 4px;
  }
</style>

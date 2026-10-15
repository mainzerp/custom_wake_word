<script lang="ts">
  import Waveform from "./Waveform.svelte";
  import { player } from "../lib/player.svelte";

  let {
    url,
    label,
    detail = "",
    note = "",
    miss = false,
  }: { url: string; label: string; detail?: string; note?: string; miss?: boolean } = $props();

  const active = $derived(player.key === url);
</script>

<button class="mini" class:miss class:playing={active && player.playing} onclick={() => player.play(url, url)} title={note || detail || label}>
  <Waveform {url} height={40} buckets={80} progress={active && player.playing ? player.progress : null} />
  <span class="meta mono"><span class="label">{label}</span><span class="faint">{detail}</span></span>
  {#if note}<span class="note">“{note}”</span>{/if}
</button>

<style>
  .mini {
    display: flex;
    flex-direction: column;
    gap: 6px;
    padding: 8px;
    border-radius: 12px;
    border: 1px solid var(--line);
    background: rgba(5, 4, 16, 0.4);
    text-align: left;
    min-width: 0;
  }
  .mini.miss {
    border-color: rgba(255, 61, 242, 0.45);
  }
  .mini.playing {
    border-color: var(--cyan);
    box-shadow: 0 0 22px -6px rgba(41, 240, 255, 0.7);
  }
  .meta {
    display: flex;
    justify-content: space-between;
    gap: 6px;
    font-size: 11px;
    color: var(--text-dim);
    white-space: nowrap;
  }
  .label {
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .note {
    font-size: 11.5px;
    color: var(--text-dim);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .miss .note {
    color: var(--magenta);
  }
</style>

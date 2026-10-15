<script lang="ts">
  import Waveform from "./Waveform.svelte";
  import { player } from "../lib/player.svelte";

  let { url, label, detail = "" }: { url: string; label: string; detail?: string } = $props();

  const active = $derived(player.key === url);
</script>

<button class="mini" class:playing={active && player.playing} onclick={() => player.play(url, url)} title={detail || label}>
  <Waveform {url} height={40} buckets={80} progress={active && player.playing ? player.progress : null} />
  <span class="meta mono"><span>{label}</span><span class="faint">{detail}</span></span>
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
    overflow: hidden;
  }
</style>

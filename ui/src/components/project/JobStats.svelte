<script lang="ts">
  import { duration, finishAt } from "../../lib/format";
  import { STALE_AFTER } from "../../lib/jobs";
  import type { Job } from "../../lib/types";

  let {
    job,
    running,
    dropTitle,
    dropNote = "",
  }: { job: Job; running: boolean; dropTitle: string; dropNote?: string } = $props();

  const loading = $derived(running && job.phase === "loading");
  const pct = $derived(job.total ? Math.min(100, ((job.done ?? 0) / job.total) * 100) : 0);
  const added = $derived((job.done ?? 0) - (job.start ?? 0));
  const stale = $derived(running && !loading && (job.age ?? 0) > STALE_AFTER);
</script>

{#if loading}
  <p class="dim small"><span class="spin"></span>{job.message ?? "Loading the model"} · {duration(job.elapsed)}</p>
{:else}
  <div class="stats mono">
    <span><strong>{(job.done ?? 0).toLocaleString()}</strong> / {(job.total ?? 0).toLocaleString()} ({pct.toFixed(1)}%)</span>
    <span title="New clips in this run">+{added.toLocaleString()} this run</span>
    <span>{job.rate ?? 0} clips/s</span>
    <span class="faint" title={dropTitle}>{(job.rejected ?? 0) + (job.filtered ?? 0)} dropped{dropNote ? ` (${dropNote})` : ""}</span>
  </div>
  <div class="stats mono">
    {#if running}
      <span>running {duration(job.elapsed)}</span>
      <span class="eta">ETA {duration(job.eta)}</span>
      <span title="Estimated finish time at the current rate">done ≈ {finishAt(job.eta)}</span>
    {:else if job.elapsed != null}
      <span>{job.state} after {duration(job.elapsed)}</span>
    {/if}
  </div>
{/if}
{#if stale}
  <p class="hint warn">No progress update for {duration(job.age)}. The worker may hang; check the log.</p>
{/if}

<style>
  .stats {
    display: flex;
    gap: 22px;
    flex-wrap: wrap;
    font-size: 13px;
    color: var(--text-dim);
  }
  .stats strong {
    color: var(--text);
    font-weight: 600;
  }
  .eta {
    color: var(--cyan);
  }
  .small {
    margin: 0;
    font-size: 13px;
    display: flex;
    align-items: center;
    gap: 8px;
  }
  .hint {
    font-size: 12.5px;
    margin: 0;
  }
  .warn {
    color: var(--amber);
  }
  .spin {
    width: 12px;
    height: 12px;
    border-radius: 50%;
    border: 2px solid rgba(41, 240, 255, 0.25);
    border-top-color: var(--cyan);
    animation: spin 0.8s linear infinite;
  }
  @keyframes spin {
    to {
      transform: rotate(360deg);
    }
  }
</style>

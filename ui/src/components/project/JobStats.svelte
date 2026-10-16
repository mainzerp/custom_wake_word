<script lang="ts">
  import { duration, finishAt } from "../../lib/format";
  import { locale, t } from "../../lib/i18n.svelte";
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
  <p class="dim small"><span class="spin"></span>{job.message ? t(job.message) : t("Loading the model")} · {duration(job.elapsed)}</p>
{:else}
  <div class="stats mono">
    <span><strong>{(job.done ?? 0).toLocaleString(locale())}</strong> / {(job.total ?? 0).toLocaleString(locale())} ({pct.toFixed(1)}%)</span>
    <span title={t("New clips in this run")}>{t("+{n} this run", { n: added })}</span>
    <span>{t("{rate} clips/s", { rate: job.rate ?? 0 })}</span>
    <span class="faint" title={dropTitle}>{dropNote
        ? t("{n} dropped ({note})", { n: (job.rejected ?? 0) + (job.filtered ?? 0), note: dropNote })
        : t("{n} dropped", { n: (job.rejected ?? 0) + (job.filtered ?? 0) })}</span>
  </div>
  <div class="stats mono">
    {#if running}
      <span>{t("running {time}", { time: duration(job.elapsed) })}</span>
      <span class="eta">{t("ETA {time}", { time: duration(job.eta) })}</span>
      <span title={t("Estimated finish time at the current rate")}>{t("done ≈ {time}", { time: finishAt(job.eta) })}</span>
    {:else if job.elapsed != null}
      <span>{t("{state} after {time}", { state: t(job.state), time: duration(job.elapsed) })}</span>
    {/if}
  </div>
{/if}
{#if stale}
  <p class="hint warn">{t("No progress update for {time}. The worker may hang; check the log.", { time: duration(job.age) })}</p>
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

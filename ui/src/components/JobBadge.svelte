<script lang="ts">
  import { jobs } from "../lib/api";
  import { duration } from "../lib/format";
  import { t } from "../lib/i18n.svelte";
  import { STALE_AFTER, summarize } from "../lib/jobs";
  import { href } from "../lib/router.svelte";
  import type { Job } from "../lib/types";

  const BASE_TITLE = document.title;
  let job = $state<Job | null>(null);
  const sum = $derived(job ? summarize(job) : null);
  const stale = $derived(!!job && job.phase !== "loading" && (job.age ?? 0) > STALE_AFTER);

  // Poll every second while a job runs (like the step pages), every 5 s otherwise.
  $effect(() => {
    let timer: ReturnType<typeof setTimeout>;
    let alive = true;
    const tick = async () => {
      try {
        job = (await jobs.active()).job;
      } catch {
        job = null;
      }
      if (alive) timer = setTimeout(tick, job ? 1000 : 5000);
    };
    tick();
    return () => {
      alive = false;
      clearTimeout(timer);
    };
  });

  $effect(() => {
    document.title = sum ? `${sum.pct != null ? `${Math.floor(sum.pct)}%` : "…"} ${sum.label} · ${BASE_TITLE}` : BASE_TITLE;
  });
</script>

{#if job && sum}
  <a
    class="badge"
    class:stale
    href={sum.step === "setup" ? href.setup : href.project(job.project, sum.step)}
    title={(job.kind === "setup" ? t("{label}: {detail}, running for {time}", { label: sum.label, detail: sum.detail, time: duration(job.elapsed) })
      : t("{label} for “{project}”: {detail}, running for {time}", { label: sum.label, project: job.project, detail: sum.detail, time: duration(job.elapsed) }))
      + (stale ? ` · ${t("no progress for {time}", { time: duration(job.age) })}` : "")}
  >
    <span class="dot"></span>
    <span class="what"><strong>{sum.label}</strong> {#if job.kind !== "setup"}<span class="dim">{job.project}</span>{/if}</span>
    <span class="bar" class:indeterminate={sum.pct == null}><span style:width="{sum.pct ?? 100}%"></span></span>
    <span class="mono num">{sum.pct != null ? `${Math.floor(sum.pct)}%` : sum.detail}</span>
    {#if sum.eta != null}<span class="mono dim num">{t("ETA {time}", { time: duration(sum.eta) })}</span>{/if}
  </a>
{/if}

<style>
  .badge {
    display: inline-flex;
    align-items: center;
    gap: 10px;
    padding: 6px 12px;
    border-radius: var(--radius-sm);
    border: 1px solid rgba(41, 240, 255, 0.35);
    background: rgba(41, 240, 255, 0.06);
    color: var(--text);
    text-decoration: none;
    font-size: 13px;
    white-space: nowrap;
    transition: background 0.15s, border-color 0.15s;
  }
  .badge:hover {
    background: rgba(41, 240, 255, 0.12);
    border-color: var(--cyan);
  }
  .badge.stale {
    border-color: var(--amber);
  }
  .dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: var(--cyan);
    box-shadow: var(--glow-cyan);
    animation: blink 1s steps(2) infinite;
  }
  .stale .dot {
    background: var(--amber);
    box-shadow: none;
  }
  .what strong {
    font-weight: 600;
  }
  .bar {
    position: relative;
    width: 110px;
    height: 6px;
    border-radius: 3px;
    background: rgba(155, 107, 255, 0.18);
    overflow: hidden;
  }
  .bar span {
    position: absolute;
    inset: 0 auto 0 0;
    background: linear-gradient(90deg, var(--cyan), var(--magenta));
    transition: width 0.6s ease-out;
  }
  .bar.indeterminate span {
    opacity: 0.5;
    animation: pulse 1.4s ease-in-out infinite;
  }
  .num {
    font-size: 12.5px;
  }
  @keyframes blink {
    50% {
      opacity: 0.25;
    }
  }
  @keyframes pulse {
    50% {
      opacity: 0.15;
    }
  }
  @media (max-width: 760px) {
    .what .dim,
    .bar {
      display: none;
    }
  }
</style>

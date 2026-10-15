<script lang="ts">
  import { untrack } from "svelte";
  import Icon from "../../components/Icon.svelte";
  import MiniClip from "../../components/MiniClip.svelte";
  import { generate, jobs } from "../../lib/api";
  import { href } from "../../lib/router.svelte";
  import { app, toast, toastError } from "../../lib/state.svelte";
  import type { GenClip, GenerateParams, GenerateStatus, Project } from "../../lib/types";

  let { project }: { project: Project } = $props();

  const DEFAULTS: GenerateParams = {
    count: 50000,
    length_scale: { lo: 0.55, hi: 1.0 },
    noise_scale: { lo: 0.3, hi: 0.8 },
    noise_w: { lo: 0.2, hi: 0.5 },
  };
  const PRESETS = [10000, 25000, 50000, 100000];

  let status = $state<GenerateStatus | null>(null);
  let params = $state<GenerateParams>(structuredClone(DEFAULTS));
  let advanced = $state(false);
  let showLog = $state(false);
  let busy = $state(false);
  let previews = $state<Record<string, GenClip[]>>({});
  let previewing = $state<string | null>(null);
  let samples = $state<GenClip[]>([]);

  const job = $derived(status?.job ?? null);
  const running = $derived(!!job && job.alive && (job.state === "running" || job.state === "starting"));
  const otherJob = $derived(status?.active && status.active.project !== project.slug ? status.active : null);
  const total = $derived(status?.corpus.total ?? 0);
  const pct = $derived(job?.total ? Math.min(100, ((job.done ?? 0) / job.total) * 100) : 0);
  const startPct = $derived(job?.total ? ((job.start ?? 0) / job.total) * 100 : 0);
  const phrasesChanged = $derived(
    !!status?.corpus.total && project.tts_phrases.some((p) => !status!.corpus.phrases.includes(p)),
  );

  async function refresh() {
    try {
      const wasRunning = running;
      const s = await generate.status();
      if (!status && s.job?.params?.count) params = { ...structuredClone(DEFAULTS), ...s.job.params } as GenerateParams;
      status = s;
      if (app.project?.slug === project.slug) app.project.summary.generated = s.corpus.total;
      if (wasRunning && s.job && !s.job.alive) {
        if (s.job.state === "failed") toastError(s.job.message ?? "Generation failed");
        else toast(s.job.state === "done" ? `Done: ${s.corpus.total.toLocaleString()} synthetic clips.` : "Generation stopped.");
        if (s.corpus.total) drawSamples();
      }
    } catch (e) {
      toastError(e);
    }
  }

  $effect(() => {
    untrack(refresh);
    const id = setInterval(() => (running || otherJob) && refresh(), 1000);
    return () => clearInterval(id);
  });

  async function act<T>(fn: () => Promise<T>) {
    busy = true;
    try {
      return await fn();
    } catch (e) {
      toastError(e);
    } finally {
      busy = false;
    }
  }

  async function start() {
    const j = await act(() => generate.start($state.snapshot(params)));
    if (j) {
      showLog = false;
      await refresh();
    }
  }

  async function stop() {
    if (job) await act(() => jobs.stop(job.id));
    await refresh();
  }

  async function reset() {
    if (!confirm(`Delete all ${total.toLocaleString()} synthetic clips of "${project.wake_word}"? Own recordings are not affected.`)) return;
    const s = await act(() => generate.reset());
    if (s) {
      status = s;
      samples = [];
      if (app.project) app.project.summary.generated = 0;
      toast("Synthetic corpus deleted.");
    }
  }

  async function preview(phrase: string) {
    previewing = phrase;
    try {
      const res = await generate.preview(phrase, $state.snapshot(params.length_scale));
      const t = Date.now();
      previews[phrase] = res.clips.map((c) => ({ ...c, url: `${c.url}?t=${t}` }));
    } catch (e) {
      toastError(e);
    } finally {
      previewing = null;
    }
  }

  async function drawSamples() {
    const res = await act(() => generate.samples(12));
    if (res) samples = res.clips;
  }

  const fmtEta = (s: number | null | undefined) =>
    s == null ? "–" : s >= 3600 ? `${Math.floor(s / 3600)}h ${Math.round((s % 3600) / 60)}m` : s >= 60 ? `${Math.floor(s / 60)}m ${s % 60}s` : `${s}s`;
  const hours = (s: number) => (s / 3600).toFixed(1);
  const startLabel = $derived(
    total >= params.count ? "Target reached" : total ? `Continue to ${params.count.toLocaleString()}` : `Generate ${params.count.toLocaleString()} clips`,
  );

  $effect(() => {
    if (status && status.corpus.total && !samples.length) untrack(drawSamples);
  });
</script>

{#if status && !status.voice}
  <section class="panel note">
    <span class="chip warn"><span class="dot"></span>No voice</span>
    <p>
      There is no multi-speaker Piper voice for this language yet (available: German, English, French, Dutch).
      Change the language in <a href={href.project(project.slug, "wakeword")}>step 1</a> or rely on own recordings.
    </p>
  </section>
{:else if status}
<div class="page">
  <div class="top">
    <section class="panel run">
      <div class="head">
        <span class="eyebrow">Run</span>
        <span class="chip mono" title="Piper voice">{status.voice?.name} · {status.voice?.speakers} speakers</span>
      </div>

      <div class="field-block">
        <span class="label">Target clips</span>
        <div class="presets">
          {#each PRESETS as p (p)}
            <button class="small" class:sel={params.count === p} onclick={() => (params.count = p)} disabled={running}>{p / 1000}k</button>
          {/each}
          <input type="number" class="mono" min="100" step="1000" bind:value={params.count} disabled={running} aria-label="Target clips" />
        </div>
        <p class="hint faint">Generation tops the corpus up to this number, so you can always continue later.</p>
      </div>

      <div class="field-block">
        <span class="label">Tempo <span class="faint">(length scale, lower = faster)</span></span>
        <div class="range">
          <input type="number" class="mono" step="0.05" min="0.3" max="2" bind:value={params.length_scale.lo} disabled={running} aria-label="Tempo min" />
          <span class="faint">to</span>
          <input type="number" class="mono" step="0.05" min="0.3" max="2" bind:value={params.length_scale.hi} disabled={running} aria-label="Tempo max" />
        </div>
      </div>

      <button class="ghost toggle" onclick={() => (advanced = !advanced)}>
        <Icon name="sliders" size={16} /> Variation
        <span class="chev" class:open={advanced}><Icon name="chevron" size={14} /></span>
      </button>
      {#if advanced}
        <div class="adv">
          <span class="label">Noise scale <span class="faint">(voice variation)</span></span>
          <div class="range">
            <input type="number" class="mono" step="0.05" bind:value={params.noise_scale.lo} disabled={running} aria-label="Noise scale min" />
            <span class="faint">to</span>
            <input type="number" class="mono" step="0.05" bind:value={params.noise_scale.hi} disabled={running} aria-label="Noise scale max" />
          </div>
          <span class="label">Noise W <span class="faint">(rhythm variation; high values create long outliers)</span></span>
          <div class="range">
            <input type="number" class="mono" step="0.05" bind:value={params.noise_w.lo} disabled={running} aria-label="Noise W min" />
            <span class="faint">to</span>
            <input type="number" class="mono" step="0.05" bind:value={params.noise_w.hi} disabled={running} aria-label="Noise W max" />
          </div>
          <button class="ghost small" onclick={() => (params = { ...structuredClone(DEFAULTS), count: params.count })} disabled={running}>
            Restore defaults
          </button>
        </div>
      {/if}

      <div class="actions">
        {#if running}
          <button class="danger" onclick={stop} disabled={busy}><Icon name="stop" size={15} /> Stop</button>
        {:else}
          <button class="primary" onclick={start} disabled={busy || !!otherJob || total >= params.count}>
            <Icon name="sparkles" size={16} /> {startLabel}
          </button>
        {/if}
      </div>
      {#if otherJob}
        <p class="hint warn">The GPU is busy: {otherJob.kind} job of "{otherJob.project}" is running.</p>
      {/if}
      {#if phrasesChanged}
        <p class="hint warn">New spellings were added since the last run; they are used for newly generated clips only.</p>
      {/if}
    </section>

    <section class="panel progress">
      <div class="head">
        <span class="eyebrow">Corpus</span>
        {#if job}
          <span class="chip {job.state === 'failed' ? 'neg' : running ? 'pos' : ''}">
            <span class="dot" class:blink={running}></span>{job.state}
          </span>
        {/if}
      </div>
      <div class="big">
        <div><strong class="mono">{(running ? Math.max(total, job?.done ?? 0) : total).toLocaleString()}</strong><span class="dim">clips</span></div>
        <div><strong class="mono">{hours(status.corpus.seconds)}</strong><span class="dim">hours of audio</span></div>
      </div>

      {#if job}
        <div class="bar" aria-label="Progress {pct.toFixed(0)}%">
          <span class="prev" style:width="{startPct}%"></span>
          <span class="fill" class:live={running} style:left="{startPct}%" style:width="{Math.max(0, pct - startPct)}%"></span>
        </div>
        <div class="stats mono">
          <span>{(job.done ?? 0).toLocaleString()} / {(job.total ?? 0).toLocaleString()}</span>
          <span>{job.rate ?? 0} clips/s</span>
          <span>ETA {running ? fmtEta(job.eta) : "–"}</span>
          <span class="faint">{job.rejected ?? 0} rejected</span>
        </div>
        {#if job.state === "failed" && job.message}
          <p class="hint err">{job.message}</p>
        {/if}
        <button class="ghost toggle" onclick={() => (showLog = !showLog)}>
          Log <span class="chev" class:open={showLog}><Icon name="chevron" size={14} /></span>
        </button>
        {#if showLog}
          <pre class="log mono">{job.log || "(empty)"}</pre>
        {/if}
      {:else}
        <p class="dim">No run yet. ~240 clips/s on the RTX 3090, so 50k clips take about 4 minutes.</p>
      {/if}
      {#if total && !running}
        <button class="danger small reset" onclick={reset} disabled={busy}><Icon name="trash" size={14} /> Delete corpus</button>
      {/if}
    </section>
  </div>

  <section class="panel block">
    <div class="head">
      <div>
        <span class="eyebrow">Pronunciation check</span>
        <p class="dim sub">Six random speakers per spelling. If it sounds wrong, adjust the spellings in step 1.</p>
      </div>
      <a class="small-link" href={href.project(project.slug, "wakeword")}>Edit spellings</a>
    </div>
    {#each project.tts_phrases as phrase (phrase)}
      <div class="phrase">
        <div class="phrase-head">
          <strong>{phrase}</strong>
          <button class="small" onclick={() => preview(phrase)} disabled={!!previewing}>
            <Icon name={previewing === phrase ? "replay" : "play"} size={14} />
            {previewing === phrase ? "Synthesizing…" : previews[phrase] ? "New voices" : "Preview"}
          </button>
        </div>
        {#if previews[phrase]}
          <div class="grid">
            {#each previews[phrase] as c (c.url)}
              <MiniClip url={c.url} label="spk {c.speaker}" detail="{c.seconds}s" />
            {/each}
          </div>
        {/if}
      </div>
    {/each}
  </section>

  {#if total}
    <section class="panel block">
      <div class="head">
        <div>
          <span class="eyebrow">Listen to the corpus</span>
          <p class="dim sub">Random clips from the generated set. Click to play.</p>
        </div>
        <button class="small" onclick={drawSamples} disabled={busy}><Icon name="replay" size={14} /> Draw 12</button>
      </div>
      <div class="grid">
        {#each samples as c (c.url)}
          <MiniClip url={c.url} label="spk {c.speaker}" detail="{c.seconds}s · ×{c.scales?.[1]}" />
        {/each}
      </div>
    </section>
  {/if}
</div>
{/if}

<style>
  .page {
    display: flex;
    flex-direction: column;
    gap: 22px;
  }
  .top {
    display: grid;
    grid-template-columns: minmax(320px, 420px) 1fr;
    gap: 22px;
    align-items: start;
  }
  .run,
  .progress,
  .block,
  .note {
    padding: 20px 22px;
    display: flex;
    flex-direction: column;
    gap: 14px;
  }
  .head {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 12px;
  }
  .label {
    font-size: 12.5px;
    color: var(--text-dim);
  }
  .field-block,
  .adv {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  .presets {
    display: flex;
    gap: 6px;
    flex-wrap: wrap;
  }
  .presets input {
    width: 110px;
  }
  .sel {
    border-color: var(--cyan);
    color: var(--cyan);
    background: rgba(41, 240, 255, 0.1);
  }
  .range {
    display: flex;
    align-items: center;
    gap: 8px;
  }
  .range input {
    width: 90px;
  }
  .hint {
    font-size: 12.5px;
    margin: 0;
    line-height: 1.5;
  }
  .hint.warn {
    color: var(--amber);
  }
  .hint.err {
    color: var(--danger);
  }
  .toggle {
    display: flex;
    align-items: center;
    gap: 8px;
    align-self: flex-start;
    padding: 4px 6px;
  }
  .chev {
    display: inline-flex;
    transition: transform 0.2s;
  }
  .chev.open {
    transform: rotate(90deg);
  }
  .actions button {
    display: inline-flex;
    align-items: center;
    gap: 8px;
  }
  .big {
    display: flex;
    gap: 40px;
  }
  .big div {
    display: flex;
    flex-direction: column;
    gap: 2px;
  }
  .big strong {
    font-size: 34px;
    font-weight: 600;
    color: var(--cyan);
    text-shadow: var(--glow-cyan);
  }
  .bar {
    position: relative;
    height: 12px;
    border-radius: 6px;
    background: rgba(155, 107, 255, 0.14);
    overflow: hidden;
  }
  .bar span {
    position: absolute;
    top: 0;
    bottom: 0;
    left: 0;
  }
  .prev {
    background: rgba(155, 107, 255, 0.45);
  }
  .fill {
    background: linear-gradient(90deg, var(--cyan), var(--magenta));
    box-shadow: 0 0 14px rgba(41, 240, 255, 0.6);
    transition: width 0.6s ease-out;
  }
  .fill.live {
    background-size: 200% 100%;
    animation: flow 1.5s linear infinite;
    background-image: linear-gradient(90deg, var(--cyan), var(--magenta), var(--cyan));
  }
  @keyframes flow {
    to {
      background-position: -200% 0;
    }
  }
  .stats {
    display: flex;
    gap: 22px;
    flex-wrap: wrap;
    font-size: 13px;
    color: var(--text-dim);
  }
  .blink {
    animation: blink 1s steps(2) infinite;
  }
  @keyframes blink {
    50% {
      opacity: 0.2;
    }
  }
  .log {
    margin: 0;
    max-height: 220px;
    overflow: auto;
    padding: 12px;
    border-radius: 10px;
    border: 1px solid var(--line);
    background: rgba(5, 4, 16, 0.6);
    font-size: 11.5px;
    white-space: pre-wrap;
    color: var(--text-dim);
  }
  .reset {
    align-self: flex-start;
    display: inline-flex;
    align-items: center;
    gap: 6px;
  }
  .sub {
    margin: 4px 0 0;
    font-size: 13px;
  }
  .small-link {
    color: var(--cyan);
    font-size: 13px;
    text-decoration: none;
  }
  .phrase {
    display: flex;
    flex-direction: column;
    gap: 10px;
    padding-top: 12px;
    border-top: 1px solid var(--line);
  }
  .phrase-head {
    display: flex;
    align-items: center;
    gap: 14px;
  }
  .phrase-head strong {
    font-family: var(--font-display);
    font-weight: 600;
  }
  .phrase-head button {
    display: inline-flex;
    align-items: center;
    gap: 6px;
  }
  .grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
    gap: 10px;
  }
  .note p {
    margin: 0;
    color: var(--text-dim);
    line-height: 1.55;
  }
  .note a {
    color: var(--cyan);
  }
  @media (max-width: 1050px) {
    .top {
      grid-template-columns: 1fr;
    }
  }
</style>

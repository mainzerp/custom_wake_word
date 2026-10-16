<script lang="ts">
  import { untrack } from "svelte";
  import Icon from "../components/Icon.svelte";
  import { projects, setupApi } from "../lib/api";
  import { duration, finishAt } from "../lib/format";
  import { locale, plural, t } from "../lib/i18n.svelte";
  import { href } from "../lib/router.svelte";
  import { toast, toastError } from "../lib/state.svelte";
  import type { JobState, Project, SetupItem, SetupStatus, SetupUse } from "../lib/types";

  let status = $state<SetupStatus | null>(null);
  let shards = $state(1);
  let busy = $state(false);
  let showLog = $state(false);
  let list = $state<Project[]>([]);
  let importFile = $state<File | null>(null);
  let importSlug = $state("");
  let importing = $state(false);

  const job = $derived(status?.job ?? null);
  const running = $derived(!!job && job.alive && (job.state === "running" || job.state === "starting"));
  const blocker = $derived(status?.active && status.active.id !== job?.id ? status.active : null);
  const missing = $derived(status?.items.filter((i) => i.state !== "ready") ?? []);
  const pct = $derived(job?.total_bytes ? Math.min(100, ((job.done_bytes ?? 0) / job.total_bytes) * 100) : 0);
  const USES: { id: SetupUse; label: string; text: string }[] = [
    { id: "training", label: "Training", text: "negative and noise datasets" },
    { id: "generation", label: "Synthetic samples", text: "voices and TTS models" },
    { id: "mining", label: "Mining", text: "German speech and the checker models" },
  ];

  async function refresh(n?: number) {
    try {
      const wasRunning = running;
      const s = await setupApi.status(n ?? shards);
      if (!status) shards = Math.max(1, s.speech_shards.have);
      status = s;
      if (wasRunning && s.job && !s.job.alive) {
        if (s.job.state === "done") toast(t("All data is ready."));
        else if (s.job.state === "failed") toastError(s.job.message ? jobMessage(s.job.message) : t("Setup failed, see the log"));
        else toast(t("Setup stopped; start again to resume where it stopped."));
      }
    } catch (e) {
      toastError(e);
    }
  }

  $effect(() => {
    untrack(() => {
      refresh();
      projects.list().then((r) => (list = r.projects), toastError);
    });
    const id = setInterval(() => (running || blocker) && refresh(), 2500);
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
    if (await act(() => setupApi.start([], shards))) {
      showLog = false;
      await refresh();
    }
  }

  async function stop() {
    await act(() => setupApi.stop());
    await refresh();
  }

  async function changeShards(n: number) {
    shards = n;
    await refresh(n);
  }

  async function doImport() {
    if (!importFile) return;
    importing = true;
    try {
      const p = await setupApi.importProject(importFile, importSlug.trim() || undefined);
      toast(t("Imported \"{name}\".", { name: p.wake_word }));
      importFile = null;
      importSlug = "";
      list = (await projects.list()).projects;
    } catch (e) {
      toastError(e);
    } finally {
      importing = false;
    }
  }

  const gb = (b: number) =>
    b >= 1e9
      ? `${(b / 1e9).toLocaleString(locale(), { maximumFractionDigits: 1, minimumFractionDigits: 1 })} GB`
      : b >= 1e6
        ? `${Math.round(b / 1e6).toLocaleString(locale())} MB`
        : b
          ? "<1 MB"
          : "–";
  const stateLabel = (s: JobState) =>
    ({ starting: t("starting"), running: t("running"), done: t("done"), stopped: t("stopped"), failed: t("failed") })[s] ?? s;
  // Job messages from trainer/setup.py: the static ones are translated, dynamic ones (file names) stay English.
  const jobMessage = (m: string) => {
    const n = m.match(/^(\d+) items to prepare$/);
    if (n) return t("{n} items to prepare", { n: Number(n[1]) });
    const known: Record<string, string> = {
      "all data is ready": t("all data is ready"),
      "stopped; start again to resume": t("stopped; start again to resume"),
      "some items are incomplete, see the log": t("some items are incomplete, see the log"),
      "downloading the model weights (about 6 GB)": t("downloading the model weights (about 6 GB)"),
      "building the voice bank on the GPU": t("building the voice bank on the GPU"),
    };
    return known[m] ?? m;
  };
  const itemJob = (i: SetupItem) => job?.items?.[i.id];
  const itemPct = (i: SetupItem) => {
    const j = itemJob(i);
    return j && j.total ? Math.min(100, (j.bytes / j.total) * 100) : null;
  };
</script>

<div class="page">
  <header class="page-head">
    <h1>{t("Data")}</h1>
    <p class="dim">
      {t("The shared datasets, voices and models every wake word uses. They live in")} <span class="mono">data/</span>
      {t("on this machine and are not part of the repository, so a new computer downloads them here once (about 50 GB; projects keep their own clips).")}
    </p>
  </header>

  {#if status}
    <section class="panel uses">
      {#each USES as u (u.id)}
        <div class="use" class:ok={status.ready_for[u.id]}>
          <span class="badge"><Icon name={status.ready_for[u.id] ? "check" : "x"} size={15} stroke={2.4} /></span>
          <span><strong>{t(u.label)}</strong><span class="dim">{status.ready_for[u.id] ? t("ready") : t("needs {what}", { what: t(u.text) })}</span></span>
        </div>
      {/each}
      <div class="disk mono">
        <span class="faint">{t("disk free")}</span> <strong>{gb(status.disk.free)}</strong>
        {#if missing.length}<span class="faint"> · {t("still needed")}</span> <strong class:warn={status.needed.disk > status.disk.free}>{gb(status.needed.disk)}</strong>{/if}
      </div>
    </section>

    <section class="panel run">
      <div class="head">
        <div>
          <span class="eyebrow">{t("Download and prepare")}</span>
          <p class="dim sub">
            {#if missing.length}
              {t("{n} of {total} items are missing: {size} to download.", { n: missing.length, total: status.items.length, size: gb(status.needed.download) })}
              {t("Everything runs in the background, resumes after an interruption and is checked against fixed checksums; archives are deleted after unpacking.")}
            {:else}
              {t("Everything is here. More German speech for mining can be added below.")}
            {/if}
          </p>
        </div>
        {#if job}
          <span class="chip {job.state === 'failed' ? 'neg' : running ? 'pos' : ''}"><span class="dot" class:blink={running}></span>{stateLabel(job.state)}</span>
        {/if}
      </div>

      <div class="shards">
        <span class="label">{t("German speech for mining")} <span class="faint">{t("(Kartoffelphon shards, about 33 h and 0.5 GB each; the first one also feeds the voice bank)")}</span></span>
        <div class="presets">
          {#each [1, 3, 6, status.speech_shards.total] as n (n)}
            <button class="small" class:sel={shards === n} onclick={() => changeShards(n)} disabled={running}>
              {n} · {n * status.speech_shards.hours_each} h
            </button>
          {/each}
        </div>
      </div>

      <div class="actions">
        {#if running}
          <button class="danger" onclick={stop} disabled={busy}><Icon name="stop" size={15} /> {t("Stop")}</button>
        {:else}
          <button class="primary" onclick={start} disabled={busy || !missing.length || !!blocker}>
            <Icon name="download" size={16} /> {missing.length ? t("Download {size}", { size: gb(status.needed.download) }) : t("Nothing to download")}
          </button>
        {/if}
        {#if blocker}<span class="hint warn">{t("Busy: {kind} job of \"{project}\" is running.", { kind: blocker.kind, project: blocker.project })}</span>{/if}
      </div>

      {#if job && (running || job.state !== "done")}
        <div class="bar"><span class="fill" class:live={running} style:width="{pct}%"></span></div>
        <div class="stats mono">
          <span><strong>{gb(job.done_bytes ?? 0)}</strong> / {gb(job.total_bytes ?? 0)}</span>
          {#if running}
            <span>{gb(job.rate ?? 0)}/s</span>
            <span>{t("ETA {time}", { time: duration(job.eta) })}</span>
            <span>{t("done ≈ {time}", { time: finishAt(job.eta) })}</span>
            <span>{t("running {time}", { time: duration(job.elapsed) })}</span>
          {:else if job.elapsed != null}
            <span>{t("{state} after {time}", { state: stateLabel(job.state), time: duration(job.elapsed) })}</span>
          {/if}
        </div>
        {#if job.message}<p class="dim small">{jobMessage(job.message)}</p>{/if}
        <p class="faint small">{t("The ETA counts downloads only; converting audio adds a few minutes per dataset.")}</p>
      {/if}
      {#if job}
        <button class="ghost toggle" onclick={() => (showLog = !showLog)}>
          {t("Log")} <span class="chev" class:open={showLog}><Icon name="chevron" size={14} /></span>
        </button>
        {#if showLog}<pre class="log mono">{job.log || t("(empty)")}</pre>{/if}
      {/if}

      <table class="items">
        <thead><tr><th>{t("Item")}</th><th>{t("Needed for")}</th><th class="num">{t("Download")}</th><th class="num">{t("On disk")}</th><th>{t("License")}</th><th>{t("State")}</th></tr></thead>
        <tbody>
          {#each status.items as i (i.id)}
            {@const j = itemJob(i)}
            <tr>
              <td><strong>{t(i.label)}</strong><span class="faint purpose">{t(i.purpose)}</span></td>
              <td class="faint">{i.needed_for.map((u) => t(USES.find((x) => x.id === u)?.label ?? u)).join(", ")}</td>
              <td class="num mono">{gb(i.download)}</td>
              <td class="num mono">{gb(i.disk)}</td>
              <td class="faint small">{t(i.license)}</td>
              <td class="state">
                {#if j && j.state === "running"}
                  <span class="chip pos"><span class="dot blink"></span>{itemPct(i) != null && itemPct(i)! < 100 ? `${Math.floor(itemPct(i)!)}%` : j.files ? plural(j.files, "{n} file", "{n} files") : t("working")}</span>
                {:else if i.state === "ready"}
                  <span class="chip pos">{t("ready")}</span>
                {:else if i.state === "partial"}
                  <span class="chip warn" title={t("{have} of {want}", { have: i.have, want: i.want })}>{t("partial {have}/{want}", { have: i.have, want: i.want })}</span>
                {:else}
                  <span class="chip neg">{t("missing")}</span>
                {/if}
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    </section>
  {/if}

  <section class="panel move">
    <span class="eyebrow">{t("Move projects to another computer")}</span>
    <ol class="steps">
      <li>{t("On the new computer: clone the repository and start the container")} (<span class="mono">docker compose up -d --build</span>).</li>
      <li>{t("Open this page there and download the data above.")}</li>
      <li>{t("Export each project here and import the .zip there. Recordings, synthetic clips, sound-alikes, mined clips and models move along.")}</li>
    </ol>
    <div class="cols">
      <div>
        <span class="label">{t("Export")}</span>
        {#each list as p (p.slug)}
          <div class="proj">
            <a href={href.project(p.slug)}>{p.wake_word}</a>
            <a class="small-btn" href={setupApi.exportUrl(p.slug)} download><Icon name="download" size={14} /> .zip</a>
          </div>
        {:else}
          <p class="faint small">{t("No projects on this machine yet.")}</p>
        {/each}
        <p class="faint small">{t("Large projects take a moment before the download starts (the .zip is built first).")}</p>
      </div>
      <div>
        <span class="label">{t("Import")}</span>
        <input type="file" accept=".zip,application/zip" onchange={(e) => (importFile = (e.currentTarget as HTMLInputElement).files?.[0] ?? null)} />
        <input type="text" placeholder={t("new name (only if it exists here already)")} bind:value={importSlug} />
        <button class="small" onclick={doImport} disabled={!importFile || importing}>
          <Icon name="plus" size={14} /> {importing ? t("Importing…") : t("Import project")}
        </button>
      </div>
    </div>
  </section>
</div>

<style>
  .page {
    display: flex;
    flex-direction: column;
    gap: 22px;
  }
  h1 {
    font-size: 30px;
    font-weight: 700;
  }
  .page-head p {
    margin: 6px 0 0;
    max-width: 860px;
    line-height: 1.55;
  }
  .uses {
    display: flex;
    gap: 18px;
    align-items: center;
    padding: 14px 18px;
    flex-wrap: wrap;
  }
  .use {
    display: flex;
    align-items: center;
    gap: 10px;
    font-size: 13px;
  }
  .use > span:last-child {
    display: flex;
    flex-direction: column;
  }
  .use .badge {
    display: grid;
    place-items: center;
    width: 28px;
    height: 28px;
    border-radius: 50%;
    border: 1px solid var(--danger);
    color: var(--danger);
  }
  .use.ok .badge {
    border-color: var(--cyan);
    color: var(--cyan);
  }
  .disk {
    margin-left: auto;
    font-size: 13px;
  }
  .warn {
    color: var(--amber);
  }
  .run,
  .move {
    padding: 20px 22px;
    display: flex;
    flex-direction: column;
    gap: 14px;
  }
  .head {
    display: flex;
    justify-content: space-between;
    gap: 16px;
    align-items: flex-start;
  }
  .sub {
    margin: 6px 0 0;
    font-size: 13px;
    line-height: 1.55;
    max-width: 860px;
  }
  .label {
    font-size: 12.5px;
    color: var(--text-dim);
    display: block;
    margin-bottom: 6px;
  }
  .presets {
    display: flex;
    gap: 6px;
    flex-wrap: wrap;
  }
  .sel {
    border-color: var(--cyan);
    color: var(--cyan);
    background: rgba(41, 240, 255, 0.1);
  }
  .actions {
    display: flex;
    align-items: center;
    gap: 14px;
  }
  .actions button {
    display: inline-flex;
    align-items: center;
    gap: 8px;
  }
  .hint {
    font-size: 12.5px;
  }
  .bar {
    position: relative;
    height: 12px;
    border-radius: 6px;
    background: rgba(155, 107, 255, 0.14);
    overflow: hidden;
  }
  .fill {
    position: absolute;
    inset: 0 auto 0 0;
    background: linear-gradient(90deg, var(--cyan), var(--magenta));
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
  .stats strong {
    color: var(--text);
  }
  .small {
    font-size: 12.5px;
    margin: 0;
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
  .log {
    margin: 0;
    max-height: 240px;
    overflow: auto;
    padding: 12px;
    border-radius: 10px;
    border: 1px solid var(--line);
    background: rgba(5, 4, 16, 0.6);
    font-size: 11.5px;
    white-space: pre-wrap;
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
  .items {
    width: 100%;
    border-collapse: collapse;
    font-size: 13px;
  }
  .items th {
    text-align: left;
    font-weight: 500;
    color: var(--text-dim);
    font-size: 12px;
    padding: 6px 10px;
    border-bottom: 1px solid var(--line);
  }
  .items td {
    padding: 9px 10px;
    border-bottom: 1px solid var(--line);
    vertical-align: top;
  }
  .items .num {
    text-align: right;
    white-space: nowrap;
  }
  .purpose {
    display: block;
    font-size: 12px;
    margin-top: 2px;
  }
  .state {
    white-space: nowrap;
  }
  .steps {
    margin: 0;
    padding-left: 20px;
    font-size: 13px;
    line-height: 1.7;
    color: var(--text-dim);
  }
  .cols {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 28px;
  }
  .cols > div {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  .proj {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    padding: 6px 0;
    border-bottom: 1px solid var(--line);
  }
  .proj a {
    color: var(--text);
    text-decoration: none;
  }
  .small-btn {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 4px 10px;
    border-radius: var(--radius-sm);
    border: 1px solid var(--line-strong);
    font-size: 12.5px;
  }
  .small-btn:hover {
    border-color: var(--cyan);
  }
  @media (max-width: 900px) {
    .cols {
      grid-template-columns: 1fr;
    }
    .items {
      display: block;
      overflow-x: auto;
    }
  }
</style>

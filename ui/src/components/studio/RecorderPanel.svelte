<script lang="ts">
  import Icon from "../Icon.svelte";
  import Scope from "../Scope.svelte";
  import { studio } from "../../lib/api";
  import { Recorder, dbToPercent } from "../../lib/audio";
  import { setCounts, toast, toastError } from "../../lib/state.svelte";
  import type { Session, SplitParams } from "../../lib/types";

  let { params = $bindable(), onuploaded }: { params: SplitParams; onuploaded: (s: Session) => void } = $props();

  const PARAM_FIELDS: { key: keyof SplitParams; label: string; step: number; hint: string }[] = [
    { key: "margin_db", label: "Margin dB", step: 1, hint: "dB above the local noise floor that counts as speech" },
    { key: "min_len", label: "Min length s", step: 0.05, hint: "shortest clip" },
    { key: "max_len", label: "Max length s", step: 0.1, hint: "longest clip" },
    { key: "merge_gap", label: "Merge gap s", step: 0.05, hint: "join parts separated by less than this" },
    { key: "pad", label: "Padding s", step: 0.05, hint: "silence kept around each word" },
    { key: "floor_window", label: "Floor window s", step: 0.5, hint: "window for the noise floor estimate" },
  ];
  const SEGMENTS = 24;

  let rec = $state<Recorder | null>(null);
  let busy = $state(false);
  let level = $state(-90);
  let elapsed = $state(0);
  let devices = $state<MediaDeviceInfo[]>([]);
  let deviceId = $state(localStorage.getItem("deviceId") ?? "");
  let prefix = $state(localStorage.getItem("prefix") ?? "");
  let showParams = $state(false);

  $effect(() => localStorage.setItem("prefix", prefix));
  $effect(() => localStorage.setItem("deviceId", deviceId));

  $effect(() => {
    if (!rec) return;
    const r = rec;
    const id = setInterval(() => {
      level = r.takePeakDb();
      elapsed = r.seconds;
    }, 80);
    return () => clearInterval(id);
  });

  async function refreshDevices() {
    const all = await navigator.mediaDevices.enumerateDevices();
    devices = all.filter((d) => d.kind === "audioinput" && d.deviceId !== "default" && d.deviceId !== "communications");
    if (deviceId && !devices.some((d) => d.deviceId === deviceId)) deviceId = "";
  }
  refreshDevices();

  async function toggle() {
    busy = true;
    try {
      if (!rec) {
        rec = await Recorder.start(deviceId);
        await refreshDevices();
      } else {
        const r = rec;
        rec = null;
        level = -90;
        const wav = await r.stop();
        const res = await studio.upload(wav, $state.snapshot(params), prefix);
        setCounts(res.counts);
        onuploaded(res.session);
        toast(`Saved ${res.session.duration}s, split into ${res.session.clips.length} clips.`);
      }
    } catch (e) {
      toastError(e);
    } finally {
      busy = false;
    }
  }

  const fmt = (s: number) => `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, "0")}`;
  const lit = $derived(Math.round((dbToPercent(level) / 100) * SEGMENTS));
</script>

<div class="panel rec" class:live={!!rec}>
  <div class="head">
    <span class="eyebrow">Recorder</span>
    <span class="chip" class:pos={!!rec}><span class="dot" class:blink={!!rec}></span>{rec ? "LIVE" : "IDLE"}</span>
  </div>

  <div class="core">
    <button class="big" class:on={!!rec} disabled={busy} onclick={toggle} aria-label={rec ? "Stop recording" : "Start recording"}>
      <span class="ring"></span>
      <Icon name={rec ? "stop" : "mic"} size={30} stroke={2} />
    </button>
    <div class="readout">
      <div class="time mono">{fmt(elapsed)}</div>
      <div class="db mono dim">{rec ? `${level.toFixed(0)} dBFS` : busy ? "uploading…" : "ready"}</div>
    </div>
  </div>

  <Scope analyser={rec?.analyser ?? null} height={80} />

  <div class="meter" aria-hidden="true">
    {#each Array(SEGMENTS) as _, i (i)}
      <span class:on={i < lit} class:warm={i >= SEGMENTS - 6} class:hot={i >= SEGMENTS - 2}></span>
    {/each}
  </div>

  <div class="fields">
    <label class="field">
      Speaker / prefix
      <input bind:value={prefix} maxlength="40" placeholder="e.g. patric" disabled={!!rec} />
    </label>
    <label class="field">
      Microphone
      <select bind:value={deviceId} disabled={!!rec}>
        <option value="">System default</option>
        {#each devices as d, i (d.deviceId)}
          <option value={d.deviceId}>{d.label || `Microphone ${i + 1}`}</option>
        {/each}
      </select>
    </label>
  </div>

  <button class="ghost toggle" onclick={() => (showParams = !showParams)}>
    <Icon name="sliders" size={16} /> Split settings
    <span class="chev" class:open={showParams}><Icon name="chevron" size={14} /></span>
  </button>
  {#if showParams}
    <div class="params">
      {#each PARAM_FIELDS as f (f.key)}
        <label class="field" title={f.hint}>
          {f.label}
          <input type="number" step={f.step} bind:value={params[f.key]} class="mono" />
        </label>
      {/each}
    </div>
  {/if}
</div>

<style>
  .rec {
    padding: 18px;
    display: flex;
    flex-direction: column;
    gap: 14px;
    transition: border-color 0.3s, box-shadow 0.3s;
  }
  .rec.live {
    border-color: rgba(255, 61, 242, 0.5);
    box-shadow: 0 0 40px -10px rgba(255, 61, 242, 0.45);
  }
  .head {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }
  .blink {
    animation: blink 1s steps(2) infinite;
  }
  @keyframes blink {
    50% {
      opacity: 0.2;
    }
  }
  .core {
    display: flex;
    align-items: center;
    gap: 18px;
  }
  .big {
    position: relative;
    width: 76px;
    height: 76px;
    border-radius: 50%;
    display: grid;
    place-items: center;
    padding: 0;
    border: 2px solid var(--magenta);
    background: radial-gradient(circle at 35% 30%, rgba(255, 61, 242, 0.35), rgba(80, 20, 90, 0.4));
    box-shadow: var(--glow-magenta);
    color: #fff;
  }
  .big:hover:not(:disabled) {
    background: radial-gradient(circle at 35% 30%, rgba(255, 61, 242, 0.5), rgba(80, 20, 90, 0.5));
    border-color: var(--magenta);
  }
  .big.on {
    border-color: var(--cyan);
    background: radial-gradient(circle at 35% 30%, rgba(41, 240, 255, 0.35), rgba(10, 60, 90, 0.4));
    box-shadow: var(--glow-cyan);
  }
  .ring {
    position: absolute;
    inset: -8px;
    border-radius: 50%;
    border: 1px solid rgba(255, 61, 242, 0.35);
  }
  .big.on .ring {
    border-color: var(--cyan);
    animation: pulse 1.4s ease-out infinite;
  }
  @keyframes pulse {
    from {
      transform: scale(0.9);
      opacity: 0.9;
    }
    to {
      transform: scale(1.35);
      opacity: 0;
    }
  }
  .time {
    font-size: 34px;
    font-weight: 600;
    letter-spacing: 0.02em;
    text-shadow: 0 0 18px rgba(155, 107, 255, 0.6);
  }
  .db {
    font-size: 13px;
  }
  .meter {
    display: grid;
    grid-template-columns: repeat(24, 1fr);
    gap: 3px;
  }
  .meter span {
    height: 8px;
    border-radius: 2px;
    background: rgba(155, 107, 255, 0.12);
    transition: background 0.06s;
  }
  .meter span.on {
    background: var(--cyan);
    box-shadow: 0 0 8px rgba(41, 240, 255, 0.7);
  }
  .meter span.on.warm {
    background: var(--amber);
    box-shadow: 0 0 8px rgba(255, 181, 71, 0.7);
  }
  .meter span.on.hot {
    background: var(--danger);
    box-shadow: 0 0 8px rgba(255, 79, 123, 0.8);
  }
  .fields {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 10px;
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
  .params {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 10px;
  }
</style>

<script lang="ts">
  import { loadPeaks, type Peaks } from "../lib/audio";

  export interface Region {
    id: string;
    start: number;
    end: number;
    color: string;
    active?: boolean;
  }

  let {
    url,
    height = 64,
    buckets = 400,
    colors = ["#29f0ff", "#9b6bff"],
    regions = [],
    progress = null,
    dim = false,
    onseek,
    onregion,
  }: {
    url: string;
    height?: number;
    buckets?: number;
    colors?: [string, string];
    regions?: Region[];
    progress?: number | null;
    dim?: boolean;
    onseek?: (seconds: number) => void;
    onregion?: (id: string) => void;
  } = $props();

  let canvas: HTMLCanvasElement;
  let width = $state(0);
  let peaks = $state<Peaks | null>(null);
  let failed = $state(false);

  $effect(() => {
    const u = url;
    peaks = null;
    failed = false;
    loadPeaks(u, buckets).then((p) => u === url && (peaks = p), () => (failed = true));
  });

  $effect(() => {
    draw(peaks, width, regions, progress, dim, colors);
  });

  function draw(p: Peaks | null, w: number, regs: Region[], prog: number | null, isDim: boolean, [c1, c2]: [string, string]) {
    if (!canvas || !w) return;
    const dpr = window.devicePixelRatio || 1;
    canvas.width = Math.round(w * dpr);
    canvas.height = Math.round(height * dpr);
    const ctx = canvas.getContext("2d")!;
    ctx.scale(dpr, dpr);
    ctx.clearRect(0, 0, w, height);
    const mid = height / 2;

    if (p) {
      for (const r of regs) {
        const x0 = (r.start / p.duration) * w;
        const x1 = (r.end / p.duration) * w;
        ctx.fillStyle = r.color + (r.active ? "38" : "1c");
        ctx.fillRect(x0, 0, x1 - x0, height);
        ctx.fillStyle = r.color + (r.active ? "ff" : "99");
        ctx.fillRect(x0, 0, x1 - x0, r.active ? 3 : 2);
      }
    }

    ctx.strokeStyle = "rgba(155,107,255,0.18)";
    ctx.beginPath();
    ctx.moveTo(0, mid);
    ctx.lineTo(w, mid);
    ctx.stroke();
    if (!p) return;

    const n = p.values.length;
    const bar = Math.max(1, w / n);
    // Normalize to the 99th percentile so a single click or pop does not flatten everything else.
    const sorted = Float32Array.from(p.values).sort();
    const max = Math.max(1e-4, sorted[Math.floor((sorted.length - 1) * 0.99)]);
    const grad = ctx.createLinearGradient(0, 0, w, 0);
    grad.addColorStop(0, c1);
    grad.addColorStop(1, c2);
    ctx.fillStyle = grad;
    ctx.shadowColor = c1;
    ctx.shadowBlur = isDim ? 0 : 8;
    ctx.globalAlpha = isDim ? 0.45 : 1;
    for (let i = 0; i < n; i++) {
      const h = Math.max(1, Math.min(1, p.values[i] / max) * (mid - 2));
      ctx.fillRect(i * bar, mid - h, Math.max(1, bar - 0.6), h * 2);
    }
    ctx.globalAlpha = 1;
    ctx.shadowBlur = 0;

    if (prog !== null && prog > 0) {
      const x = prog * w;
      ctx.fillStyle = "rgba(5,4,13,0.45)";
      ctx.fillRect(x, 0, w - x, height);
      ctx.fillStyle = "#fff";
      ctx.shadowColor = "#fff";
      ctx.shadowBlur = 10;
      ctx.fillRect(x - 1, 0, 2, height);
      ctx.shadowBlur = 0;
    }
  }

  function click(e: MouseEvent) {
    if (!peaks) return;
    const rect = canvas.getBoundingClientRect();
    const t = ((e.clientX - rect.left) / rect.width) * peaks.duration;
    const hit = regions.find((r) => t >= r.start && t <= r.end);
    if (hit && onregion) onregion(hit.id);
    else onseek?.(t);
  }
</script>

<div class="wave" bind:clientWidth={width} style:height="{height}px" class:clickable={!!(onseek || onregion)}>
  <canvas bind:this={canvas} style:width="{width}px" style:height="{height}px" onclick={click}></canvas>
  {#if failed}<span class="err">audio unavailable</span>{/if}
</div>

<style>
  .wave {
    position: relative;
    width: 100%;
  }
  .clickable canvas {
    cursor: pointer;
  }
  canvas {
    display: block;
  }
  .err {
    position: absolute;
    inset: 0;
    display: grid;
    place-items: center;
    font-size: 12px;
    color: var(--text-faint);
  }
</style>

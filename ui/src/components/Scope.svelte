<script lang="ts">
  let { analyser = null, height = 90 }: { analyser?: AnalyserNode | null; height?: number } = $props();

  let canvas: HTMLCanvasElement;
  let width = $state(0);

  $effect(() => {
    const node = analyser;
    const w = width;
    if (!canvas || !w) return;
    const dpr = window.devicePixelRatio || 1;
    canvas.width = Math.round(w * dpr);
    canvas.height = Math.round(height * dpr);
    const ctx = canvas.getContext("2d")!;
    ctx.scale(dpr, dpr);
    const buf = new Float32Array(node?.fftSize ?? 1024);
    let raf = 0;
    let t = 0;

    const frame = () => {
      ctx.clearRect(0, 0, w, height);
      const mid = height / 2;
      if (node) node.getFloatTimeDomainData(buf);
      else for (let i = 0; i < buf.length; i++) buf[i] = Math.sin(i / 40 + t) * 0.04 * Math.sin(i / 300 + t / 3);
      t += 0.05;

      const grad = ctx.createLinearGradient(0, 0, w, 0);
      grad.addColorStop(0, "#29f0ff");
      grad.addColorStop(0.5, "#9b6bff");
      grad.addColorStop(1, "#ff3df2");
      for (const [blur, alpha, lw] of [[18, 0.35, 4], [0, 1, 1.6]] as const) {
        ctx.beginPath();
        for (let i = 0; i < buf.length; i++) {
          const x = (i / (buf.length - 1)) * w;
          const y = mid + buf[i] * mid * 0.95;
          i ? ctx.lineTo(x, y) : ctx.moveTo(x, y);
        }
        ctx.strokeStyle = grad;
        ctx.lineWidth = lw;
        ctx.globalAlpha = node ? alpha : alpha * 0.5;
        ctx.shadowColor = "#29f0ff";
        ctx.shadowBlur = blur;
        ctx.stroke();
      }
      ctx.globalAlpha = 1;
      ctx.shadowBlur = 0;
      raf = requestAnimationFrame(frame);
    };
    frame();
    return () => cancelAnimationFrame(raf);
  });
</script>

<div class="scope" bind:clientWidth={width} style:height="{height}px">
  <canvas bind:this={canvas} style:width="{width}px" style:height="{height}px"></canvas>
</div>

<style>
  .scope {
    width: 100%;
    border-radius: 12px;
    background:
      repeating-linear-gradient(90deg, rgba(155, 107, 255, 0.07) 0 1px, transparent 1px 24px),
      repeating-linear-gradient(0deg, rgba(155, 107, 255, 0.07) 0 1px, transparent 1px 18px),
      rgba(5, 4, 16, 0.55);
    border: 1px solid var(--line);
    overflow: hidden;
  }
  canvas {
    display: block;
  }
</style>

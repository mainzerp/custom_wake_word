<script lang="ts">
  import Icon from "./components/Icon.svelte";
  import Studio from "./pages/Studio.svelte";
  import Soon from "./pages/Soon.svelte";
  import { counts, toasts } from "./lib/state.svelte";

  const PAGES = [
    { id: "studio", label: "Studio", icon: "mic", title: "Sample Studio", sub: "Record takes, split them, sort every clip." },
    { id: "training", label: "Training", icon: "pulse", title: "Training", sub: "Generate, featurize, train, calibrate, export." },
    { id: "mining", label: "Mining", icon: "radar", title: "Hard-Negative Mining", sub: "Hunt false triggers and feed them back." },
    { id: "models", label: "Models", icon: "cube", title: "Models", sub: "Compare runs and ship them to ESPHome." },
  ] as const;

  type PageId = (typeof PAGES)[number]["id"];
  const fromHash = (): PageId => (PAGES.find((p) => `#${p.id}` === location.hash)?.id ?? "studio");
  let page = $state<PageId>(fromHash());
  const current = $derived(PAGES.find((p) => p.id === page)!);

  $effect(() => {
    const onHash = () => (page = fromHash());
    addEventListener("hashchange", onHash);
    return () => removeEventListener("hashchange", onHash);
  });
</script>

<div class="shell">
  <nav class="rail">
    <a class="logo" href="#studio" aria-label="Wakeforge">
      <svg viewBox="0 0 32 32" width="30" height="30" aria-hidden="true">
        <defs>
          <linearGradient id="lg" x1="0" x2="1">
            <stop offset="0" stop-color="#29f0ff" /><stop offset="1" stop-color="#ff3df2" />
          </linearGradient>
        </defs>
        <path d="M3 16h4l3-9 4 18 4-14 3 8 2-3h6" fill="none" stroke="url(#lg)" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round" />
      </svg>
    </a>
    {#each PAGES as p (p.id)}
      <a class="nav" class:active={page === p.id} href="#{p.id}" title={p.title}>
        <Icon name={p.icon} size={20} />
        <span>{p.label}</span>
      </a>
    {/each}
  </nav>

  <main>
    <header>
      <div>
        <div class="brand">WAKE<span>FORGE</span></div>
        <h1>{current.title}</h1>
        <p class="dim">{current.sub}</p>
      </div>
      <div class="stats">
        <div class="stat pos">
          <span class="eyebrow">Positive</span>
          <strong class="mono">{counts.positive}</strong>
        </div>
        <div class="stat neg">
          <span class="eyebrow">Negative</span>
          <strong class="mono">{counts.negative}</strong>
        </div>
      </div>
    </header>

    {#if page === "studio"}
      <Studio />
    {:else}
      <Soon page={page} />
    {/if}
  </main>
</div>

<div class="toasts" aria-live="polite">
  {#each toasts as t (t.id)}
    <div class="toast panel" class:error={t.kind === "error"}>{t.text}</div>
  {/each}
</div>

<style>
  .shell {
    display: grid;
    grid-template-columns: 84px 1fr;
    min-height: 100vh;
  }

  .rail {
    position: sticky;
    top: 0;
    height: 100vh;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 6px;
    padding: 18px 0;
    border-right: 1px solid var(--line);
    background: linear-gradient(180deg, rgba(10, 8, 32, 0.85), rgba(5, 4, 13, 0.6));
    backdrop-filter: blur(12px);
  }

  .logo {
    display: grid;
    place-items: center;
    width: 52px;
    height: 52px;
    margin-bottom: 18px;
    border-radius: 16px;
    background: rgba(155, 107, 255, 0.08);
    border: 1px solid var(--line-strong);
    filter: drop-shadow(0 0 10px rgba(41, 240, 255, 0.35));
  }

  .nav {
    position: relative;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 5px;
    width: 68px;
    padding: 10px 0 8px;
    border-radius: 14px;
    color: var(--text-faint);
    text-decoration: none;
    font-size: 11px;
    letter-spacing: 0.04em;
    transition: color 0.15s, background 0.15s;
  }

  .nav:hover {
    color: var(--text);
    background: rgba(255, 255, 255, 0.04);
  }

  .nav.active {
    color: var(--cyan);
    background: rgba(41, 240, 255, 0.08);
    text-shadow: 0 0 12px rgba(41, 240, 255, 0.6);
  }

  .nav.active::before {
    content: "";
    position: absolute;
    left: -8px;
    top: 14px;
    bottom: 14px;
    width: 3px;
    border-radius: 3px;
    background: var(--cyan);
    box-shadow: var(--glow-cyan);
  }

  main {
    padding: 26px 32px 48px;
    min-width: 0;
  }

  header {
    display: flex;
    justify-content: space-between;
    align-items: flex-end;
    gap: 24px;
    margin-bottom: 24px;
  }

  .brand {
    font-family: var(--font-display);
    font-weight: 800;
    font-size: 12px;
    letter-spacing: 0.4em;
    color: var(--text-dim);
    margin-bottom: 8px;
  }

  .brand span {
    background: linear-gradient(90deg, var(--cyan), var(--magenta));
    -webkit-background-clip: text;
    background-clip: text;
    color: transparent;
  }

  h1 {
    font-size: 30px;
    font-weight: 700;
    background: linear-gradient(90deg, #fff 30%, #c9b8ff);
    -webkit-background-clip: text;
    background-clip: text;
    color: transparent;
  }

  header p {
    margin: 6px 0 0;
  }

  .stats {
    display: flex;
    gap: 12px;
  }

  .stat {
    display: flex;
    flex-direction: column;
    gap: 2px;
    min-width: 116px;
    padding: 10px 16px;
    border-radius: 14px;
    border: 1px solid var(--line);
    background: var(--panel);
  }

  .stat strong {
    font-size: 26px;
    font-weight: 600;
  }

  .stat.pos strong {
    color: var(--cyan);
    text-shadow: var(--glow-cyan);
  }

  .stat.neg strong {
    color: var(--magenta);
    text-shadow: var(--glow-magenta);
  }

  .toasts {
    position: fixed;
    right: 24px;
    bottom: 24px;
    display: flex;
    flex-direction: column;
    gap: 10px;
    z-index: 50;
  }

  .toast {
    padding: 12px 16px;
    max-width: 420px;
    border-color: rgba(41, 240, 255, 0.4);
    animation: slide 0.25s ease-out;
  }

  .toast.error {
    border-color: var(--danger);
    color: #ffd0dc;
  }

  @keyframes slide {
    from {
      opacity: 0;
      transform: translateY(10px);
    }
  }
</style>

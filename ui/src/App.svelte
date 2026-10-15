<script lang="ts">
  import Icon from "./components/Icon.svelte";
  import Home from "./pages/Home.svelte";
  import NewProject from "./pages/NewProject.svelte";
  import Project from "./pages/Project.svelte";
  import { href, router } from "./lib/router.svelte";
  import { toasts } from "./lib/state.svelte";

  const route = $derived(router.route);
</script>

<div class="shell">
  <nav class="topbar">
    <a class="logo" href={href.home} aria-label="Wakeforge home">
      <svg viewBox="0 0 32 32" width="28" height="28" aria-hidden="true">
        <defs>
          <linearGradient id="lg" x1="0" x2="1">
            <stop offset="0" stop-color="#29f0ff" /><stop offset="1" stop-color="#ff3df2" />
          </linearGradient>
        </defs>
        <path d="M3 16h4l3-9 4 18 4-14 3 8 2-3h6" fill="none" stroke="url(#lg)" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round" />
      </svg>
      <span class="brand">WAKE<span>FORGE</span></span>
    </a>
    {#if route.view !== "new"}
      <a class="newbtn" href={href.new}><Icon name="plus" size={16} /> New wake word</a>
    {/if}
  </nav>

  <main>
    {#if route.view === "home"}
      <header class="page-head">
        <h1>Wake words</h1>
        <p class="dim">Pick a wake word to continue, or start a new one.</p>
      </header>
      <Home />
    {:else if route.view === "new"}
      <NewProject />
    {:else}
      <Project slug={route.slug} step={route.step} />
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
    min-height: 100vh;
  }

  .topbar {
    position: sticky;
    top: 0;
    z-index: 20;
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 12px 32px;
    border-bottom: 1px solid var(--line);
    background: linear-gradient(180deg, rgba(10, 8, 32, 0.9), rgba(5, 4, 13, 0.7));
    backdrop-filter: blur(12px);
  }

  .logo {
    display: flex;
    align-items: center;
    gap: 12px;
    text-decoration: none;
    filter: drop-shadow(0 0 10px rgba(41, 240, 255, 0.3));
  }

  .brand {
    font-family: var(--font-display);
    font-weight: 800;
    font-size: 13px;
    letter-spacing: 0.4em;
    color: var(--text-dim);
  }

  .brand span {
    background: linear-gradient(90deg, var(--cyan), var(--magenta));
    -webkit-background-clip: text;
    background-clip: text;
    color: transparent;
  }

  .newbtn {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 7px 14px;
    border-radius: var(--radius-sm);
    border: 1px solid var(--line-strong);
    color: var(--text);
    text-decoration: none;
    font-size: 14px;
    transition: background 0.15s, border-color 0.15s;
  }

  .newbtn:hover {
    background: rgba(155, 107, 255, 0.12);
    border-color: var(--violet);
  }

  main {
    padding: 26px 32px 48px;
    max-width: 1500px;
    margin: 0 auto;
  }

  .page-head {
    margin-bottom: 24px;
  }

  h1 {
    font-size: 30px;
    font-weight: 700;
    background: linear-gradient(90deg, #fff 30%, #c9b8ff);
    -webkit-background-clip: text;
    background-clip: text;
    color: transparent;
  }

  .page-head p {
    margin: 6px 0 0;
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

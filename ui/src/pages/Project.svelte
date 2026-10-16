<script lang="ts">
  import { untrack } from "svelte";
  import Icon from "../components/Icon.svelte";
  import BorrowNegatives from "../components/project/BorrowNegatives.svelte";
  import Stepper from "../components/project/Stepper.svelte";
  import Soon from "./Soon.svelte";
  import Studio from "./Studio.svelte";
  import Generate from "./steps/Generate.svelte";
  import WakeWord from "./steps/WakeWord.svelte";
  import { projects } from "../lib/api";
  import { href } from "../lib/router.svelte";
  import { STEPS, nextStep, stepIndex, type StepId } from "../lib/steps";
  import { app, setProject, toastError } from "../lib/state.svelte";
  import { LANGUAGES } from "../lib/types";

  let { slug, step }: { slug: string; step: StepId | null } = $props();

  let missing = $state(false);
  const project = $derived(app.project?.slug === slug ? app.project : null);
  const current = $derived(step ?? (project ? nextStep(project) : null));
  const info = $derived(current ? STEPS[stepIndex(current)] : null);
  const prev = $derived(current ? STEPS[stepIndex(current) - 1] : undefined);
  const next = $derived(current ? STEPS[stepIndex(current) + 1] : undefined);

  $effect(() => {
    const s = slug;
    untrack(() => {
      missing = false;
      if (app.project?.slug === s) return;
      setProject(null);
      projects
        .get(s)
        .then((p) => slug === s && setProject(p))
        .catch((e) => {
          missing = true;
          toastError(e);
        });
    });
  });

  $effect(() => {
    if (project && !step) location.replace(href.project(project.slug, nextStep(project)));
  });
</script>

{#if missing}
  <section class="panel empty">
    <h2>Project not found</h2>
    <p class="dim"><a href={href.home}>Back to all wake words</a></p>
  </section>
{:else if project && current && info}
  <div class="project">
    <header>
      <div>
        <a class="crumb" href={href.home}><Icon name="grid" size={14} /> All wake words</a>
        <h1>{project.wake_word}</h1>
        <div class="meta">
          <span class="chip">{LANGUAGES[project.language] ?? project.language}</span>
          {#each project.tts_phrases.filter((p) => p !== project.wake_word) as p (p)}<span class="chip pos" title="TTS spelling">{p}</span>{/each}
        </div>
      </div>
      <div class="stats">
        <div class="stat pos"><span class="eyebrow">Positive</span><strong class="mono">{project.summary.positive}</strong></div>
        <div class="stat neg"><span class="eyebrow">Negative</span><strong class="mono">{project.summary.negative}</strong></div>
        <div class="stat"><span class="eyebrow">Synthetic</span><strong class="mono">{project.summary.generated.toLocaleString()}</strong></div>
      </div>
    </header>

    <Stepper {project} {current} />

    <div class="step-head">
      <div>
        <span class="eyebrow">Step {stepIndex(current) + 1} of {STEPS.length}{"optional" in info && info.optional ? " · optional" : ""}</span>
        <h2>{info.label}</h2>
        <p class="dim">{info.sub}</p>
      </div>
    </div>

    {#key project.slug}
      {#if current === "wakeword"}
        <WakeWord {project} />
      {:else if current === "generate"}
        <Generate {project} />
      {:else if current === "record"}
        <Studio />
        <BorrowNegatives {project} />
      {:else}
        <Soon step={current} />
      {/if}
    {/key}

    <footer>
      {#if prev}
        <a class="navbtn" href={href.project(project.slug, prev.id)}><Icon name="back" size={16} /> {prev.label}</a>
      {:else}
        <span></span>
      {/if}
      {#if next}
        <a class="navbtn primary" href={href.project(project.slug, next.id)}>Next: {next.label} <Icon name="next" size={16} /></a>
      {/if}
    </footer>
  </div>
{/if}

<style>
  .project {
    display: flex;
    flex-direction: column;
    gap: 22px;
  }
  header {
    display: flex;
    justify-content: space-between;
    align-items: flex-end;
    gap: 24px;
    flex-wrap: wrap;
  }
  .crumb {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    font-size: 12.5px;
    color: var(--text-dim);
    text-decoration: none;
  }
  .crumb:hover {
    color: var(--cyan);
  }
  h1 {
    font-size: 32px;
    font-weight: 700;
    margin: 8px 0 10px;
    background: linear-gradient(90deg, #fff 30%, #c9b8ff);
    -webkit-background-clip: text;
    background-clip: text;
    color: transparent;
  }
  .meta {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
  }
  .stats {
    display: flex;
    gap: 12px;
  }
  .stat {
    display: flex;
    flex-direction: column;
    gap: 2px;
    min-width: 110px;
    padding: 10px 16px;
    border-radius: 14px;
    border: 1px solid var(--line);
    background: var(--panel);
  }
  .stat strong {
    font-size: 24px;
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
  .step-head h2 {
    font-size: 22px;
    margin-top: 6px;
  }
  .step-head p {
    margin: 6px 0 0;
  }
  footer {
    display: flex;
    justify-content: space-between;
    padding-top: 18px;
    border-top: 1px solid var(--line);
  }
  .navbtn {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    padding: 9px 16px;
    border-radius: var(--radius-sm);
    border: 1px solid var(--line-strong);
    color: var(--text);
    text-decoration: none;
    background: rgba(255, 255, 255, 0.04);
    transition: background 0.15s, border-color 0.15s;
  }
  .navbtn:hover {
    background: rgba(155, 107, 255, 0.12);
    border-color: var(--violet);
  }
  .navbtn.primary {
    background: linear-gradient(135deg, rgba(41, 240, 255, 0.18), rgba(155, 107, 255, 0.18));
    border-color: var(--cyan);
    box-shadow: var(--glow-cyan);
  }
  .empty {
    padding: 48px;
    text-align: center;
  }
  .empty a {
    color: var(--cyan);
  }
</style>

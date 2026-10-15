<script lang="ts">
  import Icon from "../Icon.svelte";
  import { href } from "../../lib/router.svelte";
  import { STEPS, stepState, type StepId } from "../../lib/steps";
  import type { Project } from "../../lib/types";

  let { project, current }: { project: Project; current: StepId } = $props();
</script>

<nav class="stepper" aria-label="Workflow">
  {#each STEPS as s, i (s.id)}
    {@const st = stepState(s.id, project)}
    <a
      class="step"
      class:on={s.id === current}
      class:done={st.done}
      class:soon={!s.available}
      href={href.project(project.slug, s.id)}
      aria-current={s.id === current ? "step" : undefined}
    >
      <span class="badge">
        {#if st.done}<Icon name="check" size={15} stroke={2.4} />{:else}<span class="mono">{i + 1}</span>{/if}
      </span>
      <span class="text">
        <span class="label">{s.label}</span>
        <span class="metric mono">{s.available ? st.metric : "soon"}</span>
      </span>
    </a>
  {/each}
</nav>

<style>
  .stepper {
    display: grid;
    grid-template-columns: repeat(6, 1fr);
    gap: 6px;
    padding: 6px;
    border-radius: var(--radius);
    border: 1px solid var(--line);
    background: var(--panel);
    backdrop-filter: blur(14px);
  }
  .step {
    position: relative;
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 10px 12px;
    border-radius: 13px;
    color: var(--text-dim);
    text-decoration: none;
    min-width: 0;
    transition: background 0.15s, color 0.15s;
  }
  .step:hover {
    background: rgba(255, 255, 255, 0.04);
    color: var(--text);
  }
  .step + .step::before {
    content: "";
    position: absolute;
    left: -5px;
    top: 50%;
    width: 4px;
    height: 1px;
    background: var(--line-strong);
  }
  .badge {
    flex: none;
    display: grid;
    place-items: center;
    width: 30px;
    height: 30px;
    border-radius: 50%;
    border: 1px solid var(--line-strong);
    font-size: 13px;
    color: var(--text-dim);
  }
  .done .badge {
    border-color: rgba(41, 240, 255, 0.6);
    color: var(--cyan);
    background: rgba(41, 240, 255, 0.08);
  }
  .on {
    background: rgba(41, 240, 255, 0.08);
    color: var(--text);
  }
  .on .badge {
    border-color: var(--cyan);
    color: #fff;
    background: rgba(41, 240, 255, 0.2);
    box-shadow: var(--glow-cyan);
  }
  .text {
    display: flex;
    flex-direction: column;
    gap: 2px;
    min-width: 0;
  }
  .label {
    font-size: 13.5px;
    font-weight: 600;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .metric {
    font-size: 11px;
    color: var(--text-faint);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .soon .metric {
    color: var(--amber);
    opacity: 0.7;
  }
  @media (max-width: 1200px) {
    .stepper {
      grid-template-columns: repeat(3, 1fr);
    }
    .step + .step::before {
      display: none;
    }
  }
</style>

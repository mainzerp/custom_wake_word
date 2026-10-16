<script lang="ts">
  import Icon from "../Icon.svelte";
  import { guide, nextText } from "../../lib/guide.svelte";
  import { t } from "../../lib/i18n.svelte";
  import { href } from "../../lib/router.svelte";
  import { STEPS, isStep, type StepId } from "../../lib/steps";

  let { slug, current }: { slug: string; current: StepId } = $props();

  const next = $derived(guide.slug === slug ? guide.data?.next ?? null : null);
  const here = $derived(next?.step === current);
  const target = $derived(next && isStep(next.step) ? STEPS.find((s) => s.id === next.step) : undefined);
  const link = $derived(next?.step === "setup" ? href.setup : target ? href.project(slug, target.id) : null);
</script>

{#if next}
  <section class="next" class:here aria-live="polite">
    <span class="icon"><Icon name={target?.icon ?? (next.step === "setup" ? "download" : "next")} size={20} /></span>
    <div class="body">
      <span class="eyebrow">{here ? t("Next step · on this page") : t("Next step · {step}", { step: target ? t(target.label) : next.step === "setup" ? t("Data") : next.step })}</span>
      <strong>{nextText(next).title}</strong>
      <p>{nextText(next).text}</p>
    </div>
    {#if !here && link}
      <a class="go" href={link}>{next.action ? t(next.action) : target ? t(target.label) : t("Open")} <Icon name="next" size={16} /></a>
    {/if}
  </section>
{/if}

<style>
  .next {
    display: flex;
    align-items: center;
    gap: 16px;
    padding: 14px 18px;
    border-radius: var(--radius);
    border: 1px solid rgba(41, 240, 255, 0.35);
    background: linear-gradient(90deg, rgba(41, 240, 255, 0.08), rgba(255, 61, 242, 0.05));
    box-shadow: inset 3px 0 0 var(--cyan);
  }
  .next.here {
    border-color: var(--line-strong);
    box-shadow: inset 3px 0 0 var(--violet);
    background: rgba(155, 107, 255, 0.06);
  }
  .icon {
    flex: none;
    display: grid;
    place-items: center;
    width: 40px;
    height: 40px;
    border-radius: 50%;
    border: 1px solid rgba(41, 240, 255, 0.45);
    color: var(--cyan);
  }
  .here .icon {
    border-color: var(--line-strong);
    color: var(--violet);
  }
  .body {
    display: flex;
    flex-direction: column;
    gap: 3px;
    min-width: 0;
    flex: 1;
  }
  strong {
    font-size: 15.5px;
    font-weight: 600;
  }
  p {
    margin: 0;
    font-size: 13px;
    line-height: 1.5;
    color: var(--text-dim);
  }
  .go {
    flex: none;
    display: inline-flex;
    align-items: center;
    gap: 8px;
    padding: 9px 16px;
    border-radius: var(--radius-sm);
    border: 1px solid var(--cyan);
    color: var(--cyan);
    background: rgba(41, 240, 255, 0.1);
    text-decoration: none;
    font-weight: 500;
    white-space: nowrap;
    transition: background 0.15s, box-shadow 0.15s;
  }
  .go:hover {
    background: rgba(41, 240, 255, 0.18);
    box-shadow: var(--glow-cyan);
  }
  @media (max-width: 760px) {
    .next {
      flex-wrap: wrap;
    }
  }
</style>

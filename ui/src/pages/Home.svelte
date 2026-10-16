<script lang="ts">
  import Icon from "../components/Icon.svelte";
  import { projects } from "../lib/api";
  import { href } from "../lib/router.svelte";
  import { STEPS, isStep, nextStep, stepState } from "../lib/steps";
  import { plural, t } from "../lib/i18n.svelte";
  import { toastError } from "../lib/state.svelte";
  import { LANGUAGES, type Project } from "../lib/types";

  let list = $state<Project[]>([]);
  let loaded = $state(false);

  projects
    .list()
    .then((r) => (list = r.projects))
    .catch(toastError)
    .finally(() => (loaded = true));

  const nextStepOf = (p: Project) => (p.next && isStep(p.next.step) ? p.next.step : nextStep(p));
  const nextLabel = (p: Project) =>
    p.next ? t(p.next.tpl.title, p.next.params) : t(STEPS.find((s) => s.id === nextStepOf(p))!.label);
  const wake = (p: Project) => p.summary.generated + p.summary.positive;
  const neg = (p: Project) => p.summary.negative + p.summary.confusable + p.summary.mined + p.summary.borrowed;
</script>

<div class="home">
  {#if loaded && !list.length}
    <section class="panel hero">
      <span class="eyebrow">{t("Welcome")}</span>
      <h2>{t("Forge your first wake word")}</h2>
      <p class="dim">
        {t("A short wizard sets the word and its pronunciation. After that a step bar walks you through synthetic samples, your own recordings, training, mining and the ESPHome export.")}
      </p>
      <a class="cta" href={href.new}><Icon name="plus" size={18} /> {t("New wake word")}</a>
    </section>
  {:else}
    <div class="grid">
      <a class="panel card new" href={href.new}>
        <span class="plus"><Icon name="plus" size={26} /></span>
        <strong>{t("New wake word")}</strong>
        <span class="dim">{t("Guided setup in four short steps")}</span>
      </a>
      {#each list as p (p.slug)}
        <a class="panel card" href={href.project(p.slug, nextStepOf(p))}>
          <div class="top">
            <span class="chip">{LANGUAGES[p.language] ? t(LANGUAGES[p.language]) : p.language}</span>
            <span class="faint mono small">{p.updated.slice(0, 10)}</span>
          </div>
          <h2>{p.wake_word}</h2>
          <div class="track" aria-label={t("Progress")}>
            {#each STEPS as s (s.id)}
              <span class:done={stepState(s.id, p).done} title="{t(s.label)}: {stepState(s.id, p).metric}"></span>
            {/each}
          </div>
          <div class="nums mono">
            <span class="pos" title={t("synthetic + own recordings")}>{t("{n} wake word", { n: wake(p) })}</span>
            <span class="neg" title={t("sound-alikes + mined + own + borrowed")}>{t("{n} negative", { n: neg(p) })}</span>
            <span>{plural(p.summary.runs, "{n} model", "{n} models")}</span>
          </div>
          <div class="next">{t("Next:")} <strong>{nextLabel(p)}</strong> <Icon name="next" size={14} /></div>
        </a>
      {/each}
    </div>
  {/if}
</div>

<style>
  .grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
    gap: 18px;
  }
  .card {
    display: flex;
    flex-direction: column;
    gap: 14px;
    padding: 20px 22px;
    color: inherit;
    text-decoration: none;
    transition: border-color 0.15s, box-shadow 0.15s, transform 0.15s;
  }
  .card:hover {
    border-color: var(--cyan);
    box-shadow: 0 0 34px -12px rgba(41, 240, 255, 0.6);
    transform: translateY(-2px);
  }
  .card h2 {
    font-size: 24px;
  }
  .top {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }
  .small {
    font-size: 12px;
  }
  .track {
    display: grid;
    grid-template-columns: repeat(6, 1fr);
    gap: 5px;
  }
  .track span {
    height: 5px;
    border-radius: 3px;
    background: rgba(155, 107, 255, 0.18);
  }
  .track span.done {
    background: var(--cyan);
    box-shadow: 0 0 8px rgba(41, 240, 255, 0.6);
  }
  .nums {
    display: flex;
    gap: 14px;
    font-size: 12.5px;
    color: var(--text-dim);
  }
  .nums .pos {
    color: var(--cyan);
  }
  .nums .neg {
    color: var(--magenta);
  }
  .next {
    display: flex;
    align-items: center;
    gap: 6px;
    margin-top: auto;
    font-size: 13px;
    color: var(--text-dim);
  }
  .next strong {
    color: var(--text);
    font-weight: 600;
  }
  .new {
    align-items: center;
    justify-content: center;
    text-align: center;
    min-height: 220px;
    border-style: dashed;
    border-color: var(--line-strong);
    gap: 8px;
  }
  .new strong {
    font-family: var(--font-display);
    font-weight: 600;
  }
  .plus {
    display: grid;
    place-items: center;
    width: 54px;
    height: 54px;
    margin-bottom: 6px;
    border-radius: 50%;
    border: 1px solid var(--cyan);
    color: var(--cyan);
    box-shadow: var(--glow-cyan);
  }
  .hero {
    max-width: 680px;
    margin: 40px auto 0;
    padding: 40px;
    text-align: center;
  }
  .hero h2 {
    font-size: 28px;
    margin: 12px 0;
  }
  .hero p {
    line-height: 1.6;
  }
  .cta {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    margin-top: 18px;
    padding: 12px 20px;
    border-radius: var(--radius-sm);
    border: 1px solid var(--cyan);
    color: var(--text);
    text-decoration: none;
    background: linear-gradient(135deg, rgba(41, 240, 255, 0.18), rgba(155, 107, 255, 0.18));
    box-shadow: var(--glow-cyan);
  }
</style>

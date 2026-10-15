<script lang="ts">
  import { untrack } from "svelte";
  import Icon from "../../components/Icon.svelte";
  import ProjectFields from "../../components/project/ProjectFields.svelte";
  import PronunciationCheck from "../../components/project/PronunciationCheck.svelte";
  import { projects } from "../../lib/api";
  import { app, setProject, toast, toastError } from "../../lib/state.svelte";
  import type { Project, ProjectSettings } from "../../lib/types";

  let { project }: { project: Project } = $props();

  const pick = (p: Project): ProjectSettings => ({
    wake_word: p.wake_word,
    language: p.language,
    tts_phrases: [...p.tts_phrases],
    author: p.author,
    website: p.website,
  });

  let settings = $state<ProjectSettings>(untrack(() => pick(project)));
  let busy = $state(false);
  const dirty = $derived(JSON.stringify(settings) !== JSON.stringify(pick(project)));

  async function save() {
    busy = true;
    try {
      const p = await projects.update(project.slug, $state.snapshot(settings));
      if (app.project?.slug === p.slug) setProject(p);
      settings = pick(p);
      toast("Settings saved.");
    } catch (e) {
      toastError(e);
    } finally {
      busy = false;
    }
  }
</script>

<div class="layout">
  <section class="panel main">
    <ProjectFields bind:settings sections={["name"]} />
    <hr />
    <ProjectFields bind:settings sections={["phrases"]} />
    <PronunciationCheck language={settings.language} phrases={settings.tts_phrases} />
    <hr />
    <ProjectFields bind:settings sections={["manifest"]} />
    <div class="actions">
      <button onclick={() => (settings = pick(project))} disabled={!dirty || busy} class="ghost">Revert</button>
      <button class="primary" onclick={save} disabled={!dirty || busy}><Icon name="check" size={16} /> Save</button>
    </div>
  </section>

  <aside class="panel tips">
    <span class="eyebrow">Good wake words</span>
    <ul>
      <li>Two to four syllables with distinct consonants (<span class="mono">Dscharwis</span>, <span class="mono">Hey Nova</span>).</li>
      <li>Rare in everyday speech, TV and music, so the model sees few look-alikes.</li>
      <li>Renaming keeps all samples. The project folder name stays <span class="mono">{project.slug}</span>.</li>
      <li>Changing spellings only affects newly generated samples.</li>
    </ul>
  </aside>
</div>

<style>
  .layout {
    display: grid;
    grid-template-columns: minmax(0, 1fr) 320px;
    gap: 22px;
    align-items: start;
  }
  .main {
    padding: 22px 24px;
    display: flex;
    flex-direction: column;
    gap: 14px;
  }
  hr {
    border: none;
    border-top: 1px solid var(--line);
    margin: 8px 0;
    width: 100%;
  }
  .actions {
    display: flex;
    justify-content: flex-end;
    gap: 10px;
    margin-top: 8px;
  }
  .actions button {
    display: inline-flex;
    align-items: center;
    gap: 6px;
  }
  .tips {
    padding: 20px 22px;
  }
  .tips ul {
    margin: 12px 0 0;
    padding-left: 18px;
    color: var(--text-dim);
    font-size: 13.5px;
    line-height: 1.6;
    display: flex;
    flex-direction: column;
    gap: 6px;
  }
  @media (max-width: 1050px) {
    .layout {
      grid-template-columns: 1fr;
    }
  }
</style>

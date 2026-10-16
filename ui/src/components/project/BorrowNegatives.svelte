<script lang="ts">
  import { projects } from "../../lib/api";
  import { href } from "../../lib/router.svelte";
  import { app, setProject, toastError } from "../../lib/state.svelte";
  import type { BorrowCandidate, BorrowEntry, Project } from "../../lib/types";

  let { project }: { project: Project } = $props();

  type Kind = "recordings" | "synthetic";
  let candidates = $state<BorrowCandidate[]>([]);
  let loaded = $state(false);
  let busy = $state(false);

  async function refresh() {
    try {
      candidates = (await projects.borrowCandidates(project.slug)).projects;
    } catch (e) {
      toastError(e);
    } finally {
      loaded = true;
    }
  }

  async function toggle(c: BorrowCandidate, kind: Kind) {
    const selected = { ...c.selected, [kind]: !c.selected[kind] };
    const entries: BorrowEntry[] = candidates
      .map((x) => ({ slug: x.slug, ...(x.slug === c.slug ? selected : x.selected) }))
      .filter((e) => e.recordings || e.synthetic);
    busy = true;
    try {
      const p = await projects.update(project.slug, { borrow_negatives: entries });
      if (app.project?.slug === p.slug) setProject(p);
      c.selected = selected;
    } catch (e) {
      toastError(e);
    } finally {
      busy = false;
    }
  }

  const kinds: { kind: Kind; label: string; count: (c: BorrowCandidate) => number }[] = [
    { kind: "recordings", label: "recordings", count: (c) => c.recordings },
    { kind: "synthetic", label: "synthetic", count: (c) => c.synthetic },
  ];

  refresh();
</script>

<section class="panel borrow">
  <div class="head">
    <div>
      <span class="eyebrow">Negatives from other projects</span>
      <p class="dim">
        Clips of your other wake words are perfect negatives here: real voices, real rooms, and a different word. They are
        referenced, not copied, so new clips in those projects count automatically.
      </p>
    </div>
    <div class="total">
      <strong class="mono">{project.summary.borrowed.toLocaleString()}</strong>
      <span class="faint">borrowed clips</span>
    </div>
  </div>

  {#if loaded && candidates.length === 0}
    <p class="faint empty">No other projects yet. <a href={href.new}>Create another wake word</a> and its clips can be used here.</p>
  {:else}
    <ul>
      {#each candidates as c (c.slug)}
        <li class:conflict={c.level === "conflict"}>
          <div class="name">
            <a href={href.project(c.slug)}>{c.wake_word}</a>
            <span class="chip">{c.language}</span>
            {#if c.level === "conflict"}
              <span class="chip neg" title="Phone distance {c.distance}">sounds like {project.wake_word}</span>
            {:else if c.level === "close"}
              <span class="chip warn" title="Phone distance {c.distance}">similar sound: hard negatives</span>
            {/if}
          </div>
          <div class="kinds">
            {#each kinds as k (k.kind)}
              <label class="check" class:off={k.count(c) === 0 && !c.selected[k.kind]}>
                <input
                  type="checkbox"
                  checked={c.selected[k.kind]}
                  disabled={busy || c.level === "conflict"}
                  onchange={() => toggle(c, k.kind)}
                />
                <span><span class="mono">{k.count(c).toLocaleString()}</span> {k.label}</span>
              </label>
            {/each}
          </div>
        </li>
      {/each}
    </ul>
    {#if candidates.some((c) => c.level === "conflict")}
      <p class="faint note">
        Projects whose wake word sounds like <span class="mono">{project.wake_word}</span> cannot be borrowed: their clips
        would teach the model that its own wake word is a negative.
      </p>
    {/if}
  {/if}
</section>

<style>
  .borrow {
    padding: 20px 22px;
    display: flex;
    flex-direction: column;
    gap: 14px;
  }
  .head {
    display: flex;
    justify-content: space-between;
    gap: 24px;
    align-items: flex-start;
  }
  .head p {
    margin: 8px 0 0;
    max-width: 640px;
    font-size: 13.5px;
    line-height: 1.5;
  }
  .total {
    display: flex;
    flex-direction: column;
    align-items: flex-end;
    white-space: nowrap;
  }
  .total strong {
    font-size: 24px;
    color: var(--magenta);
    text-shadow: var(--glow-magenta);
  }
  .total span {
    font-size: 12px;
  }
  ul {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  li {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 16px;
    flex-wrap: wrap;
    padding: 10px 14px;
    border: 1px solid var(--line);
    border-radius: var(--radius-sm);
    background: rgba(255, 255, 255, 0.02);
  }
  li.conflict {
    opacity: 0.6;
  }
  .name {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-wrap: wrap;
  }
  .name a {
    color: var(--text);
    font-weight: 600;
    text-decoration: none;
  }
  .name a:hover {
    color: var(--cyan);
  }
  .kinds {
    display: flex;
    gap: 18px;
  }
  .check {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 13px;
    cursor: pointer;
  }
  .check.off {
    color: var(--text-faint);
  }
  .check input {
    accent-color: var(--magenta);
  }
  .empty,
  .note {
    margin: 0;
    font-size: 13px;
  }
  .empty a {
    color: var(--cyan);
  }
</style>

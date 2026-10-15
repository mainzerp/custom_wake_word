<script lang="ts">
  let { step }: { step: "train" | "mining" | "export" } = $props();

  const CONTENT = {
    train: {
      milestone: "Milestone 1",
      steps: ["Featurize", "Train", "Calibrate", "Compare"],
      text: "Pick a profile (fast or thorough) and watch every stage live with progress, logs and a clean stop. Synthetic and own clips are weighted separately.",
    },
    mining: {
      milestone: "Milestone 2",
      steps: ["Scan audio", "Collect triggers", "Review", "Retrain"],
      text: "The streaming model runs over hours of German podcasts and parliament speech. Every false trigger lands here for a listen.",
    },
    export: {
      milestone: "Milestone 1",
      steps: ["Recall vs FA/h", "Operating point", "Validate", "ESPHome YAML"],
      text: "Every run with its operating point, side by side with the current model, exported as a clean ESPHome manifest plus .tflite.",
    },
  } as const;

  const c = $derived(CONTENT[step]);
</script>

<section class="panel soon">
  <span class="chip warn"><span class="dot"></span>{c.milestone}</span>
  <p>{c.text}</p>
  <ol>
    {#each c.steps as s, i (s)}
      <li style:--i={i}><span class="mono">{String(i + 1).padStart(2, "0")}</span>{s}</li>
    {/each}
  </ol>
</section>

<style>
  .soon {
    padding: 32px;
    max-width: 900px;
  }
  p {
    font-size: 17px;
    color: var(--text-dim);
    max-width: 620px;
    line-height: 1.55;
  }
  ol {
    display: flex;
    flex-wrap: wrap;
    gap: 12px;
    padding: 0;
    margin: 28px 0 0;
    list-style: none;
  }
  li {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 12px 18px;
    border-radius: 14px;
    border: 1px dashed var(--line-strong);
    color: var(--text-dim);
    animation: breathe 3s ease-in-out infinite;
    animation-delay: calc(var(--i) * 0.4s);
  }
  li span {
    color: var(--violet);
  }
  @keyframes breathe {
    50% {
      border-color: rgba(41, 240, 255, 0.5);
      color: var(--text);
    }
  }
</style>

import type { StepId } from "./steps";
import type { Job, TrainJob } from "./types";

/** Seconds without a progress write after which a running job looks stuck (a generation batch takes ~10 s). */
export const STALE_AFTER = 90;

export interface JobSummary {
  label: string;
  step: StepId;
  /** 0..100, null while there is nothing to count yet */
  pct: number | null;
  eta: number | null;
  detail: string;
}

const TRAIN_PHASES: Record<string, string> = {
  featurize: "computing features",
  train: "training",
  export: "exporting",
  calibrate: "calibrating",
};

export function summarize(job: Job): JobSummary {
  if (job.kind === "train") {
    const t = job as TrainJob;
    if (t.phase === "featurize" && t.featurize) {
      const f = t.featurize;
      return { label: "Training", step: "train", pct: f.total ? (f.done / f.total) * 100 : null, eta: f.eta, detail: TRAIN_PHASES.featurize };
    }
    const pct = t.phase === "train" && t.steps ? ((t.step ?? 0) / t.steps) * 100 : null;
    return { label: "Training", step: "train", pct, eta: t.phase === "train" ? (t.eta ?? null) : null, detail: TRAIN_PHASES[t.phase ?? ""] ?? "starting" };
  }
  const label = job.kind === "confusables" ? "Sound-alikes" : "Generating";
  if (job.phase === "loading" || !job.total) return { label, step: "generate", pct: null, eta: null, detail: "loading the model" };
  return {
    label,
    step: "generate",
    pct: Math.min(100, ((job.done ?? 0) / job.total) * 100),
    eta: job.eta ?? null,
    detail: `${(job.done ?? 0).toLocaleString()} / ${job.total.toLocaleString()}`,
  };
}

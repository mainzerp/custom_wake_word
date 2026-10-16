import { locale, plural, t } from "./i18n.svelte";
import type { StepId } from "./steps";
import type { Job, MiningJob, SetupJob, TrainJob } from "./types";

/** Seconds without a progress write after which a running job looks stuck (a generation batch takes ~10 s). */
export const STALE_AFTER = 90;

export interface JobSummary {
  label: string;
  /** the step page that shows the job; "setup" is the data page */
  step: StepId | "setup";
  /** 0..100, null while there is nothing to count yet */
  pct: number | null;
  eta: number | null;
  detail: string;
}

const TRAIN_PHASES: Record<string, string> = {
  featurize: "computing features",
  train: "training the model",
  export: "exporting",
  calibrate: "calibrating",
};

/** Label and detail come translated (call it at render time). */
export function summarize(job: Job): JobSummary {
  if (job.kind === "train") {
    const tj = job as TrainJob;
    if (tj.phase === "featurize" && tj.featurize) {
      const f = tj.featurize;
      return { label: t("Training"), step: "train", pct: f.total ? (f.done / f.total) * 100 : null, eta: f.eta, detail: t(TRAIN_PHASES.featurize) };
    }
    const pct = tj.phase === "train" && tj.steps ? ((tj.step ?? 0) / tj.steps) * 100 : null;
    const phase = TRAIN_PHASES[tj.phase ?? ""];
    return { label: t("Training"), step: "train", pct, eta: tj.phase === "train" ? (tj.eta ?? null) : null, detail: phase ? t(phase) : t("starting") };
  }
  if (job.kind === "setup") {
    const s = job as SetupJob;
    const now = Object.values(s.items ?? {}).find((i) => i.state === "running");
    return {
      label: t("Downloading data"),
      step: "setup",
      pct: s.total_bytes ? Math.min(100, ((s.done_bytes ?? 0) / s.total_bytes) * 100) : null,
      eta: s.eta ?? null,
      detail: now ? t(now.label) : t("preparing"),
    };
  }
  if (job.kind === "mining" || job.kind === "triage") {
    const m = job as MiningJob;
    if (m.phase === "triage") {
      const tr = m.triage;
      return { label: job.kind === "triage" ? t("Checking") : t("Mining"), step: "mining", pct: tr?.total ? (tr.done / tr.total) * 100 : null, eta: null, detail: t("checking triggers") };
    }
    if (m.phase === "loading" || !m.total_s) return { label: t("Mining"), step: "mining", pct: null, eta: null, detail: t("listing the audio") };
    return { label: t("Mining"), step: "mining", pct: Math.min(100, ((m.done_s ?? 0) / m.total_s) * 100), eta: m.eta ?? null, detail: plural(m.hits ?? 0, "{n} trigger", "{n} triggers") };
  }
  const label = job.kind === "confusables" ? t("Sound-alikes") : t("Generating");
  if (job.phase === "loading" || !job.total) return { label, step: "generate", pct: null, eta: null, detail: t("loading the model") };
  return {
    label,
    step: "generate",
    pct: Math.min(100, ((job.done ?? 0) / job.total) * 100),
    eta: job.eta ?? null,
    detail: `${(job.done ?? 0).toLocaleString(locale())} / ${job.total.toLocaleString(locale())}`,
  };
}

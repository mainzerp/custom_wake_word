import type { Project } from "./types";

export interface Step {
  id: string;
  label: string;
  icon: string;
  sub: string;
  available: boolean;
  optional?: boolean;
  milestone?: string;
}

export const STEPS = [
  { id: "wakeword", label: "Wake word", icon: "type", sub: "Name, language and how the TTS voices should pronounce it.", available: true },
  { id: "generate", label: "Synthetic samples", icon: "sparkles", sub: "Hundreds of Piper TTS speakers saying your wake word, generated on the GPU.", available: true },
  { id: "record", label: "Own recordings", icon: "mic", sub: "Record takes, split them, sort every clip.", available: true, optional: true },
  { id: "train", label: "Training", icon: "pulse", sub: "Featurize, train and calibrate the model.", available: false, milestone: "Milestone 1" },
  { id: "mining", label: "Mining", icon: "radar", sub: "Hunt false triggers in hours of speech and feed them back.", available: false, optional: true, milestone: "Milestone 2" },
  { id: "export", label: "Export", icon: "download", sub: "Pick an operating point and ship it to ESPHome.", available: false, milestone: "Milestone 1" },
] as const satisfies readonly Step[];

export type StepId = (typeof STEPS)[number]["id"];

export const isStep = (id: string | undefined): id is StepId => STEPS.some((s) => s.id === id);
export const stepIndex = (id: StepId) => STEPS.findIndex((s) => s.id === id);

export function stepState(id: StepId, p: Project): { done: boolean; metric: string } {
  const s = p.summary;
  switch (id) {
    case "wakeword":
      return { done: !!p.wake_word, metric: p.wake_word };
    case "generate":
      return { done: s.generated > 0, metric: `${s.generated.toLocaleString()} clips` };
    case "record":
      return { done: s.positive > 0, metric: `${s.positive} pos · ${s.negative} neg` };
    case "train":
      return { done: s.runs > 0, metric: `${s.runs} runs` };
    case "mining":
      return { done: false, metric: "after training" };
    case "export":
      return { done: s.models > 0, metric: `${s.models} models` };
  }
}

/** The step to work on next: first open step that already works, else the first open one. Mining is never "next". */
export function nextStep(p: Project): StepId {
  const open = STEPS.filter((s) => s.id !== "mining" && !stepState(s.id, p).done);
  return (open.find((s) => s.available) ?? open[0] ?? STEPS[STEPS.length - 1]).id;
}

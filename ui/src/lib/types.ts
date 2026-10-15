export type Label = "positive" | "negative";

export interface SplitParams {
  margin_db: number;
  min_len: number;
  max_len: number;
  merge_gap: number;
  pad: number;
  floor_window: number;
}

export interface Clip {
  name: string;
  start: number;
  length: number;
  clip_start?: number;
  clip_end?: number;
  peak_db: number;
  label: Label | null;
}

export interface Session {
  name: string;
  prefix: string;
  duration: number;
  rejected: number;
  params: SplitParams;
  clips: Clip[];
}

export interface Counts {
  positive: number;
  negative: number;
}

export interface ProjectSettings {
  wake_word: string;
  language: string;
  tts_phrases: string[];
  author: string;
  website: string;
}

export interface ProjectSummary extends Counts {
  sessions: number;
  generated: number;
  runs: number;
  models: number;
}

export interface Project extends ProjectSettings {
  slug: string;
  created: string;
  updated: string;
  summary: ProjectSummary;
}

export interface Range {
  lo: number;
  hi: number;
}

export interface GenerateParams {
  count: number;
  length_scale: Range;
  noise_scale: Range;
  noise_w: Range;
}

export type JobState = "starting" | "running" | "done" | "stopped" | "failed";

export interface Job {
  id: string;
  project: string;
  kind: string;
  started: string;
  params: Partial<GenerateParams>;
  state: JobState;
  alive: boolean;
  done?: number;
  start?: number;
  total?: number;
  rejected?: number;
  rate?: number;
  eta?: number | null;
  message?: string;
  log?: string;
}

export interface GenerateStatus {
  voice: { name: string; speakers: number } | null;
  corpus: { voice: string | null; phrases: string[]; total: number; seconds: number; shards: number };
  job: Job | null;
  active: Job | null;
}

export interface GenClip {
  url: string;
  speaker: number;
  seconds: number;
  phrase?: string | null;
  scales?: number[];
}

export const LANGUAGES: Record<string, string> = {
  de: "German",
  en: "English",
  fr: "French",
  es: "Spanish",
  it: "Italian",
  nl: "Dutch",
  pl: "Polish",
  pt: "Portuguese",
  sv: "Swedish",
  da: "Danish",
  no: "Norwegian",
  fi: "Finnish",
  cs: "Czech",
  tr: "Turkish",
  ru: "Russian",
  uk: "Ukrainian",
};

export const DEFAULT_PARAMS: SplitParams = {
  margin_db: 12,
  min_len: 0.3,
  max_len: 2,
  merge_gap: 0.2,
  pad: 0.15,
  floor_window: 5,
};

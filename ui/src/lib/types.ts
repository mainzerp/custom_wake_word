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

export const DEFAULT_PARAMS: SplitParams = {
  margin_db: 12,
  min_len: 0.3,
  max_len: 2,
  merge_gap: 0.2,
  pad: 0.15,
  floor_window: 5,
};

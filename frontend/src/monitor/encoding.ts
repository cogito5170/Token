// design/encoding.json (owner: design) read as-is. frontend reads these values and never makes new ones.
import raw from "../../../design/encoding.json" with { type: "json" };

export interface SignalEntry {
  signal: string;
  target: string;
  word: string | null;
  hover?: string;
  duration?: string;
  [k: string]: unknown;
}

export interface Encoding {
  words: string[];
  word_style: { size_px: number; max_on_stage_ms: number; sticky_while_true: string[]; max_per_figure: number };
  glossary_banned_on_stage: string[];
  durations_ms: Record<"instant" | "fast" | "base" | "slow" | "travel" | "breath", number>;
  reduced_motion: { max_fade_ms: number; highlight_hold_ms: number };
  figures: {
    shapes: string[];
    states: Record<string, { lightness_pct: number; outline: string; word: string | null }>;
    rings: Record<string, { shape: string; word: string | null }>;
    retired_outcome_marks: Record<string, string>;
    edge_weight_px: { min: number; max: number };
  };
  tiles: { shelves: Record<string, string>; shapes: Record<string, string> };
  moods: {
    priority: string[];
    rules: Record<"pace" | "collaboration" | "tension" | "stall" | "all_done", { lightness_delta_pct: number; word: string | null }>;
  };
  limits: { fps_max: number; particles_max: number; pulses_merge_above: number };
  signals: SignalEntry[];
}

export const encoding = raw as unknown as Encoding;

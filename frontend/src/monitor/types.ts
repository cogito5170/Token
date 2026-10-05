// Types of the live monitor: MonitorEvent (monitor-event/1, docs/data-model.md 7.2) and the scene semantics
// (gc-golden-scene/1, design/golden/README.md).

export interface MonitorEvent {
  seq: number;
  kind: string;
  observed_at: string;
  provenance?: string;
  source_file?: string;
  node?: string | null;
  peer?: string | null;
  item?: string | null;
  role?: string | null;
  data?: Record<string, unknown> | null;
}

export type Shelf = "waiting" | "held" | "done" | "failed";

export interface SceneFigure {
  node: string;
  role: string | null;
  shape_index: number;
  shape: string;
  notches: number;
  state: string;
  lightness_pct: number;
  ring: string;
  ring_shape: string;
  item: string | null;
  tether_to: string | null;
  outcome_mark: string | null;
  word: string | null;
}

export interface SceneTile {
  id: string;
  role: string | null;
  shelf: Shelf;
  band: string | null;
  holder: string | null;
  parent: string | null;
  shape: string;
}

export interface SceneEdge { a: string; b: string; pi_permille: number; messages: number; weight_px: number }

export interface SceneMood {
  pace: number;
  collaboration: boolean;
  tension: boolean;
  stall: boolean;
  all_done: boolean;
  active: string;
  tempo_permille: number;
  lightness_delta_pct: number;
}

export interface Scene {
  schema: string;
  t_ms: number;
  round: number | null;
  figures: SceneFigure[];
  tiles: SceneTile[];
  dropped_marks: string[];
  edges: SceneEdge[];
  mood: SceneMood;
  stage_word: string | null;
  words: string[];
}

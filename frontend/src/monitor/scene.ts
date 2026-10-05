// CMD-FE2: scene(events, t) for the live monitor — the TypeScript twin of design/golden/reference.py.
// Pure: same events + same t give an equal scene. t is ms since the first event's observed_at
// (design/motion.md 1); an event is in the scene when observed_at <= origin + t, ties keep seq order.
// Every value comes from design/encoding.json; nothing here invents a color, size, time or mapping.
import { encoding, type Encoding } from "./encoding";
import type { MonitorEvent, Scene, SceneEdge, SceneFigure, SceneMood, SceneTile, Shelf } from "./types";

export const SCHEMA = "gc-golden-scene/1";
const RING_BY_STATUS: Record<string, string> = { failed: "failed", needs_judgement: "needs_judgement", budget: "budget" };
export const DROPPED_SHOW_MS = 1000;

/** observed_at (ISO, UTC, ms) -> epoch ms. */
export function ms(iso: string): number {
  return Date.parse(iso);
}

/** Events in seq order (stable, like Python's sorted). */
export function bySeq(events: readonly MonitorEvent[]): MonitorEvent[] {
  return [...events].sort((a, b) => a.seq - b.seq);
}

export function origin(events: readonly MonitorEvent[]): number {
  return events.length ? ms(bySeq(events)[0].observed_at) : 0;
}

function ring(d: Record<string, unknown>): string {
  const status = d.status as string | undefined;
  if (status && status in RING_BY_STATUS) return RING_BY_STATUS[status];
  if (status === "done") return d.verified ? "verified" : "needs_judgement";
  return "none";
}

/** pi_permille 0..1000 -> lo..hi px, rounded half up (encoding figures.edge_weight_px). */
export function edgeWeight(pi: number, lo: number, hi: number): number {
  return lo + Math.floor(((hi - lo) * pi + 500) / 1000);
}

type Mood = { pace: number; collaboration: boolean; tension: boolean; stall: boolean; all_done: boolean };

export function tempoPermille(m: Mood): number {
  if (m.all_done) return 0;
  if (m.stall) return 300;
  let tempo = 500 + Math.min(m.pace, 30) * 50;
  if (m.tension) tempo = Math.floor((tempo * 1500) / 1000);
  return tempo;
}

function lightnessDelta(m: Mood, rules: Encoding["moods"]["rules"]): number {
  if (m.all_done) return rules.all_done.lightness_delta_pct;
  if (m.stall) return rules.stall.lightness_delta_pct;
  let delta = 0;
  for (const name of ["tension", "collaboration"] as const) if (m[name]) delta += rules[name].lightness_delta_pct;
  return delta;
}

const cmp = (a: string, b: string) => (a < b ? -1 : a > b ? 1 : 0);

interface Fig { node: string; role: string | null; state: string; ring: string; item: string | null; tether_to: string | null; outcome: string | null }
interface Tile { id: string; role: string | null; shelf: Shelf; holder: string | null; parent: string | null }

export function scene(events: readonly MonitorEvent[], tMs: number, enc: Encoding = encoding): Scene {
  const evs = bySeq(events);
  const now = (evs.length ? ms(evs[0].observed_at) : 0) + tMs;
  const sig = new Map(enc.signals.map((s) => [s.signal, s]));
  const states = enc.figures.states;
  const wordMax = enc.word_style.max_on_stage_ms;
  const ew = enc.figures.edge_weight_px;

  let roles: string[] = [];
  let rnd: number | null = 0;
  const figures = new Map<string, Fig>();
  const tiles = new Map<string, Tile>();
  const edges = new Map<string, { a: string; b: string; pi_permille: number; messages: number }>();
  const dropped: [number, string][] = [];
  const mood: Mood = { pace: 0, collaboration: false, tension: false, stall: false, all_done: false };
  const lastWord = new Map<string, [number, number, string]>();

  const fig = (node: string, role?: string | null): Fig => {
    let f = figures.get(node);
    if (!f) {
      f = { node, role: role ?? null, state: "running", ring: "none", item: null, tether_to: null, outcome: null };
      figures.set(node, f);
    }
    if (role && !f.role) f.role = role;
    return f;
  };
  const edge = (a: string, b: string) => {
    const [x, y] = [a, b].sort(cmp);
    const key = `${x}\u0000${y}`;
    let v = edges.get(key);
    if (!v) edges.set(key, (v = { a: x, b: y, pi_permille: 0, messages: 0 }));
    return v;
  };

  for (const e of evs) {
    const at = ms(e.observed_at);
    if (at > now) break;
    const k = e.kind;
    const d = (e.data ?? {}) as Record<string, any>;
    const node = e.node ?? null;
    if (k === "file:pool.round") {
      roles = [...((d.roles as string[]) || roles)];
      rnd = "round" in d ? d.round : rnd;
    } else if (k === "file:queue.added") {
      tiles.set(e.item!, { id: e.item!, role: e.role ?? null, shelf: "waiting", holder: null, parent: d.parent ?? null });
    } else if (k === "file:pool.live.claimed") {
      const f = fig(node!, e.role);
      f.item = e.item ?? null;
      if (f.state !== "retiring" && f.state !== "retired") f.state = "running";
      let t = tiles.get(e.item!);
      if (!t) tiles.set(e.item!, (t = { id: e.item!, role: e.role ?? null, shelf: "waiting", holder: null, parent: null }));
      t.shelf = "held";
      t.holder = node;
    } else if (k === "l0:node.started") {
      const f = fig(node!, e.role);
      f.item = e.item || f.item;
    } else if (k === "file:queue.done" || k === "file:queue.failed" || k === "l0:work.failed") {
      const tid = k !== "l0:work.failed" ? d.id : e.item;
      const t = tiles.get(tid);
      if (t) t.shelf = k === "file:queue.done" ? "done" : "failed";
    } else if (k === "l0:work.accepted") {
      const child = tiles.get(d.id);
      if (child && child.parent === null) child.parent = e.item ?? null;
    } else if (k === "l0:work.dropped") {
      dropped.push([at, d.id]);
    } else if (k === "file:node.state.consults") {
      const f = fig(node!);
      const peers = (d.peers as string[]) || [];
      if (peers.length) {
        f.state = "waiting_peer";
        f.tether_to = peers[0];
      } else if (f.state === "waiting_peer") {
        f.state = "running";
        f.tether_to = null;
      }
    } else if (k === "file:node.run.cont_open") {
      const f = fig(node!);
      if (f.state === "running" || f.state === "idle") f.state = "continuing";
    } else if (k === "file:pool.live.idle") {
      const f = fig(node!);
      if (f.state !== "retiring" && f.state !== "retired") f.state = "idle";
    } else if (k === "file:pool.live.retiring") {
      const f = fig(node!);
      if (f.state !== "retired") f.state = "retiring";
    } else if (k === "l0:node.retired") {
      const f = fig(node!, e.role);
      f.state = "retired";
      f.tether_to = null;
      f.outcome = d.outcome ?? null;
    } else if (k === "file:node.state.done") {
      fig(node!).ring = ring(d);
    } else if (k === "file:node.pi") {
      edge(node!, e.peer!).pi_permille = Math.trunc(Number(d.pi_permille ?? 0));
    } else if (k === "l0:peer.message.sent") {
      edge(node!, e.peer!).messages += 1;
    } else if (k.startsWith("derived:")) {
      const name = k.split(":")[1] as keyof Mood;
      if (name in mood) {
        const v = d.value;
        if (name === "pace") mood.pace = Math.trunc(Number(v));
        else (mood as Record<string, unknown>)[name] = Boolean(v);
      }
    }

    let word = sig.get(k)?.word ?? null;
    if (k === "file:node.state.consults" && !(d.peers && d.peers.length)) word = null; // tether released
    if (word) {
      let holder = node;
      if (holder === null && e.item && tiles.has(e.item)) holder = tiles.get(e.item)!.holder;
      if (holder !== null && sig.get(k)!.target !== "stage") lastWord.set(holder, [at, e.seq, word]);
    }
  }

  let stageWord: string | null = null;
  for (const name of enc.word_style.sticky_while_true) {
    const m = name.split(":")[1] as keyof Mood;
    if (mood[m]) {
      stageWord = enc.moods.rules[m].word;
      break;
    }
  }

  const shapes = enc.figures.shapes;
  const outFigs: SceneFigure[] = [...figures.keys()].sort(cmp).map((node) => {
    const f = figures.get(node)!;
    const idx = f.role !== null && roles.includes(f.role) ? roles.indexOf(f.role) : 0;
    const w = lastWord.get(node);
    return {
      node,
      role: f.role,
      shape_index: idx,
      shape: shapes[idx % shapes.length],
      notches: Math.floor(idx / shapes.length),
      state: f.state,
      lightness_pct: states[f.state].lightness_pct,
      ring: f.ring,
      ring_shape: enc.figures.rings[f.ring].shape,
      item: f.state !== "retired" ? f.item : null,
      tether_to: f.tether_to,
      outcome_mark: f.state === "retired" ? (enc.figures.retired_outcome_marks[f.outcome ?? ""] ?? null) : null,
      word: w && now - w[0] < wordMax ? w[2] : null,
    };
  });

  const outTiles: SceneTile[] = [...tiles.keys()].sort(cmp).map((tid) => {
    const t = tiles.get(tid)!;
    return {
      id: tid,
      role: t.role,
      shelf: t.shelf,
      band: t.shelf !== "held" ? enc.tiles.shelves[t.shelf] : null,
      holder: t.shelf === "held" ? t.holder : null,
      parent: t.parent,
      shape: enc.tiles.shapes[t.shelf],
    };
  });

  const outEdges: SceneEdge[] = [...edges.keys()].sort(cmp).map((key) => {
    const v = edges.get(key)!;
    return { ...v, weight_px: edgeWeight(v.pi_permille, ew.min, ew.max) };
  });

  const active = enc.moods.priority.find((m) => m !== "pace" && mood[m as keyof Mood]) ?? "pace";
  const wordSet = new Set<string>();
  for (const f of outFigs) if (f.word) wordSet.add(f.word);
  if (stageWord) wordSet.add(stageWord);
  const outMood: SceneMood = {
    ...mood,
    active,
    tempo_permille: tempoPermille(mood),
    lightness_delta_pct: lightnessDelta(mood, enc.moods.rules),
  };
  return {
    schema: SCHEMA,
    t_ms: tMs,
    round: rnd,
    figures: outFigs,
    tiles: outTiles,
    dropped_marks: dropped.filter(([a]) => now - a < DROPPED_SHOW_MS).map(([, i]) => i).sort(cmp),
    edges: outEdges,
    mood: outMood,
    stage_word: stageWord,
    words: [...wordSet].sort(cmp),
  };
}

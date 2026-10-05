// CMD-FE2: frame(events, t, opts) — the full display list of the stage at t. Pure, like scene():
// equal events + t + opts give an equal frame, so the canvas only draws what this returns.
// Meaning comes from scene() (design/golden); placement and motion follow design/motion.md.
import { encoding as enc } from "./encoding";
import { bySeq, ms, scene } from "./scene";
import type { MonitorEvent, Scene } from "./types";

export interface FrameOptions {
  width: number;
  height: number;
  reduced: boolean;
}

/** One drawable thing. x/y/r and the other numbers are geometry; opacity is the only value a fade may change. */
export interface El {
  id: string;
  kind: "dust" | "band" | "horizon" | "edge" | "tether" | "link" | "pulse" | "halo" | "figure" | "inner" | "ring" | "fuel" | "tile" | "rim" | "word";
  x: number;
  y: number;
  r: number;
  opacity: number;
  x2?: number;
  y2?: number;
  w?: number;
  h?: number;
  width?: number; // stroke width (px)
  shape?: string;
  notches?: number;
  ticks?: number;
  frac?: number; // fuel arc share 0..1
  warm?: boolean;
  text?: string;
  filled?: boolean;
  dotted?: boolean;
  split?: boolean;
  /** Small numbers for the hover tooltip (never drawn on stage). */
  hover?: string[];
}

export interface Frame {
  width: number;
  height: number;
  scene: Scene;
  els: El[];
}

const D = enc.durations_ms;
const SIZE = /min (\d+) px, max (\d+) px/.exec(String((enc.figures as unknown as { size: string }).size)) ?? ["", "24", "72"];
export const R_MIN = Number(SIZE[1]) / 2;
export const R_MAX = Number(SIZE[2]) / 2;
const TILE_W = 14;
const TILE_H = 10;

interface Extras {
  order: string[]; // nodes by first appearance
  tokens: Map<string, number>;
  cost: Map<string, number>;
  started: Map<string, number>; // epoch ms of the last start/claim
  changed: Map<string, number>; // epoch ms of the last visible change, per element id
  messages: { at: number; from: string; to: string }[];
  budgetUse: number | null; // 0..1
  usage: { tokens: number | null; cost: number | null; budget: number | null };
  times: number[]; // distinct event times <= now, ascending
}

function extras(evs: MonitorEvent[], now: number): Extras {
  const x: Extras = { order: [], tokens: new Map(), cost: new Map(), started: new Map(), changed: new Map(), messages: [], budgetUse: null, usage: { tokens: null, cost: null, budget: null }, times: [] };
  for (const e of evs) {
    const at = ms(e.observed_at);
    if (at > now) break;
    if (x.times[x.times.length - 1] !== at) x.times.push(at);
    const d = (e.data ?? {}) as Record<string, any>;
    const n = e.node;
    if (n && !x.order.includes(n)) x.order.push(n);
    if (n) x.changed.set(`f:${n}`, at);
    if (e.item) x.changed.set(`t:${e.item}`, at);
    if (typeof d.id === "string") x.changed.set(`t:${d.id}`, at);
    if (e.kind === "file:pool.live.claimed" || e.kind === "l0:node.started") {
      if (n) {
        if (e.kind === "file:pool.live.claimed") x.tokens.set(n, 0);
        x.started.set(n, at);
      }
    } else if ((e.kind === "file:node.budget.grow" || e.kind === "l0:run.end") && n) {
      if (typeof d.tokens === "number") x.tokens.set(n, Math.max(x.tokens.get(n) ?? 0, d.tokens));
      if (typeof d.cost_cli_microusd === "number") x.cost.set(n, d.cost_cli_microusd);
    } else if (e.kind === "l0:peer.message.sent" && n && e.peer) {
      x.messages.push({ at, from: n, to: e.peer });
      x.changed.set(`e:${[n, e.peer].sort().join("|")}`, at);
    } else if (e.kind === "file:usage.snapshot") {
      x.usage = { tokens: d.tokens_total ?? null, cost: d.cost_cli_microusd ?? null, budget: d.budget_microusd ?? null };
      if (d.budget_microusd) x.budgetUse = Math.min(1, (d.cost_cli_microusd ?? 0) / d.budget_microusd);
    }
  }
  return x;
}

type Box = { x: number; y: number; r: number };

/** Stage geometry (motion.md 2): waiting shelf top, stage middle, done shelf bottom, failed shelf right, rest rim border. */
function bands(w: number, h: number) {
  const pad = Math.max(16, Math.min(w, h) * 0.04);
  const shelf = Math.max(28, h * 0.09);
  const failedW = Math.max(40, w * 0.08);
  return {
    pad,
    waiting: { x: pad, y: pad, w: w - 2 * pad - failedW, h: shelf },
    done: { x: pad, y: h - pad - shelf, w: w - 2 * pad - failedW, h: shelf },
    failed: { x: w - pad - failedW + 8, y: pad, w: failedW - 8, h: h - 2 * pad },
    stage: { x: pad, y: pad + shelf, w: w - 2 * pad - failedW, h: h - 2 * pad - 2 * shelf },
  };
}

export function radius(tokens: number, maxTokens: number): number {
  if (maxTokens <= 0 || tokens <= 0) return R_MIN;
  return R_MIN + (R_MAX - R_MIN) * Math.sqrt(Math.sqrt(tokens / maxTokens)); // area ~ sqrt(tokens)
}

/** Resting place of every figure and tile for one scene (no motion). */
function targets(sc: Scene, x: Extras, w: number, h: number): Map<string, Box> {
  const out = new Map<string, Box>();
  const b = bands(w, h);
  const live = x.order.filter((n) => sc.figures.some((f) => f.node === n && f.state !== "retired"));
  const retired = x.order.filter((n) => sc.figures.some((f) => f.node === n && f.state === "retired"));
  const maxTok = Math.max(0, ...live.map((n) => x.tokens.get(n) ?? 0));
  const cx = b.stage.x + b.stage.w / 2;
  const cy = b.stage.y + b.stage.h / 2;
  const tight = sc.mood.collaboration ? 0.8 : 1; // springs tighten 20 %
  const rx = (b.stage.w / 2 - R_MAX) * 0.62 * tight;
  const ry = (b.stage.h / 2 - R_MAX) * 0.62 * tight;
  const pos = new Map<string, { x: number; y: number }>();
  live.forEach((n, i) => {
    const a = live.length === 1 ? Math.PI : Math.PI + (2 * Math.PI * i) / live.length;
    pos.set(n, { x: cx + (live.length === 1 ? 0 : rx * Math.cos(a)), y: cy + (live.length === 1 ? 0 : ry * Math.sin(a)) });
  });
  // pi pulls two figures closer (encoding figures.edge_distance)
  const pulled = new Map([...pos].map(([k, v]) => [k, { ...v }]));
  for (const e of sc.edges) {
    const p = pos.get(e.a), q = pos.get(e.b);
    if (!p || !q) continue;
    const k = (e.pi_permille / 1000) * 0.18;
    pulled.get(e.a)!.x += (q.x - p.x) * k; pulled.get(e.a)!.y += (q.y - p.y) * k;
    pulled.get(e.b)!.x += (p.x - q.x) * k; pulled.get(e.b)!.y += (p.y - q.y) * k;
  }
  for (const n of live) {
    const p = pulled.get(n)!;
    out.set(`f:${n}`, { x: p.x, y: p.y, r: radius(x.tokens.get(n) ?? 0, maxTok) });
  }
  // rest rim: retired figures settle in one line along the lower border
  retired.forEach((n, i) => {
    const step = Math.min(28, b.stage.w / Math.max(1, retired.length));
    out.set(`f:${n}`, { x: cx + (i - (retired.length - 1) / 2) * step, y: b.done.y - 10, r: R_MIN / 3 });
  });
  const row = (ids: string[], band: { x: number; y: number; w: number; h: number }) => {
    const step = Math.min(TILE_W + 8, band.w / Math.max(1, ids.length));
    ids.forEach((id, i) => out.set(`t:${id}`, { x: band.x + band.w / 2 + (i - (ids.length - 1) / 2) * step, y: band.y + band.h / 2, r: TILE_W / 2 }));
  };
  row(sc.tiles.filter((t) => t.shelf === "waiting").map((t) => t.id), b.waiting);
  row(sc.tiles.filter((t) => t.shelf === "done").map((t) => t.id), b.done);
  sc.tiles.filter((t) => t.shelf === "failed").forEach((t, i) => out.set(`t:${t.id}`, { x: b.failed.x + b.failed.w / 2, y: b.failed.y + 24 + i * (TILE_H + 10), r: TILE_W / 2 }));
  for (const t of sc.tiles.filter((t) => t.shelf === "held")) {
    const f = out.get(`f:${t.holder}`);
    if (f) out.set(`t:${t.id}`, { x: f.x, y: f.y + f.r + TILE_H, r: TILE_W / 2 });
  }
  return out;
}

const ease = (p: number) => (p <= 0 ? 0 : p >= 1 ? 1 : 1 - Math.pow(1 - p, 3));

/**
 * Places at `now`: each layout change travels for `travel` ms from where things were just before it.
 * Recursion only reaches back through changes still travelling (at most 4), so it is short and pure.
 */
function placed(evs: MonitorEvent[], t0: number, now: number, w: number, h: number, reduced: boolean, memo: Map<number, Map<string, Box>>, depth = 0): Map<string, Box> {
  const hit = memo.get(now);
  if (hit) return hit;
  const sc = scene(evs, now - t0);
  const x = extras(evs, now);
  const target = targets(sc, x, w, h);
  let out = target;
  const last = x.times[x.times.length - 1];
  if (!reduced && depth < 4 && last !== undefined && last > t0 && now - last < D.travel) {
    const before = placed(evs, t0, last - 1, w, h, reduced, memo, depth + 1);
    const p = ease((now - last) / D.travel);
    out = new Map();
    for (const [id, b] of target) {
      const a = before.get(id);
      out.set(id, a ? { x: a.x + (b.x - a.x) * p, y: a.y + (b.y - a.y) * p, r: a.r + (b.r - a.r) * p } : b);
    }
  }
  memo.set(now, out);
  return out;
}

function hash(i: number): number {
  let s = (i + 1) * 2654435761;
  s = Math.imul(s ^ (s >>> 16), 2246822507);
  s = Math.imul(s ^ (s >>> 13), 3266489909);
  return ((s ^ (s >>> 16)) >>> 0) / 4294967296;
}

const fmt = (n: number) => String(Math.round(n)).replace(/\B(?=(\d{3})+(?!\d))/g, ",");

export function frame(events: readonly MonitorEvent[], tMs: number, opts: FrameOptions): Frame {
  const { width: w, height: h, reduced } = opts;
  const evs = bySeq(events);
  const t0 = evs.length ? ms(evs[0].observed_at) : 0;
  const now = t0 + tMs;
  const sc = scene(evs, tMs);
  const x = extras(evs, now);
  const at = placed(evs, t0, now, w, h, reduced, new Map());
  const b = bands(w, h);
  const els: El[] = [];
  const tempo = sc.mood.tempo_permille / 1000;
  const light = 1 + sc.mood.lightness_delta_pct / 100;
  const clamp = (v: number) => Math.max(0, Math.min(1, v));
  // fade-in after a change: reduced motion uses opacity only, <= max_fade_ms (motion.md 6)
  const fadeMs = reduced ? enc.reduced_motion.max_fade_ms : D.base;
  const fade = (id: string) => {
    const c = x.changed.get(id);
    return c === undefined ? 1 : clamp((now - c) / Math.max(1, fadeMs));
  };
  const phase = (period: number, offset = 0) => Math.sin((2 * Math.PI * (tMs * Math.max(tempo, 0.05))) / period + offset);

  // dust: the amount and speed of ambient particles follows pace (moods.rules.pace)
  if (!reduced && !sc.mood.all_done) {
    const count = Math.min(enc.limits.particles_max, 20 + Math.min(sc.mood.pace, 30) * 6);
    for (let i = 0; i < count; i++) {
      const vx = (hash(i * 3) - 0.5) * 0.02 * tempo;
      const vy = (hash(i * 3 + 1) - 0.5) * 0.02 * tempo;
      const px = (((hash(i * 7) * w + vx * tMs) % w) + w) % w;
      const py = (((hash(i * 11) * h + vy * tMs) % h) + h) % h;
      els.push({ id: `d:${i}`, kind: "dust", x: px, y: py, r: 0.6 + hash(i * 5) * 1.2, opacity: 0.08 + 0.12 * hash(i * 13) });
    }
  }

  // shelves and horizon (total use vs budget as a line height; warm only under tension)
  els.push({ id: "b:waiting", kind: "band", x: b.waiting.x, y: b.waiting.y, w: b.waiting.w, h: b.waiting.h, r: 0, opacity: 0.35 });
  els.push({ id: "b:done", kind: "band", x: b.done.x, y: b.done.y, w: b.done.w, h: b.done.h, r: 0, opacity: 0.35 });
  els.push({ id: "b:failed", kind: "band", x: b.failed.x, y: b.failed.y, w: b.failed.w, h: b.failed.h, r: 0, opacity: 0.25 });
  const use = x.budgetUse ?? 0;
  els.push({
    id: "h:horizon", kind: "horizon", x: b.done.x, x2: b.done.x + b.done.w, y: b.done.y + b.done.h - use * b.done.h, r: 0,
    width: 1 + use * 2, warm: sc.mood.tension, opacity: clamp(0.4 + use * 0.5),
    hover: x.usage.budget ? [`${fmt(x.usage.tokens ?? 0)}`, `$${((x.usage.cost ?? 0) / 1e6).toFixed(2)} / $${(x.usage.budget / 1e6).toFixed(2)}`] : undefined,
  });

  const fpos = (n: string | null) => (n ? at.get(`f:${n}`) : undefined);

  // child tiles to their parent
  for (const t of sc.tiles) {
    const p = t.parent ? at.get(`t:${t.parent}`) : undefined;
    const c = at.get(`t:${t.id}`);
    if (p && c) els.push({ id: `l:${t.id}`, kind: "link", x: c.x, y: c.y, x2: p.x, y2: p.y, r: 0, width: 1, opacity: 0.18 * fade(`t:${t.id}`) });
  }

  // lines between figures: weight = pi, brighter under collaboration
  const live = new Set(sc.figures.filter((f) => f.state !== "retired").map((f) => f.node));
  for (const e of sc.edges) {
    const p = fpos(e.a), q = fpos(e.b);
    if (!p || !q || !live.has(e.a) || !live.has(e.b)) continue;
    const eid = `e:${e.a}|${e.b}`;
    const recent = x.changed.get(eid);
    // reduced motion: a message holds a highlight for highlight_hold_ms instead of a travelling pulse
    const hold = reduced && recent !== undefined && now - recent < enc.reduced_motion.highlight_hold_ms ? 0.3 : 0;
    els.push({
      id: eid, kind: "edge", x: p.x, y: p.y, x2: q.x, y2: q.y, r: 0, width: e.weight_px,
      opacity: clamp((sc.mood.collaboration ? 0.55 : 0.35) + hold),
      hover: [`${(e.pi_permille / 1000).toFixed(2)}`, `${e.messages}`],
    });
  }

  // pulses: messages travel along the line; more than pulses_merge_above in flight merge into one
  if (!reduced) {
    const flying = x.messages.filter((m) => now - m.at < D.travel && live.has(m.from) && live.has(m.to));
    const lim = enc.limits.pulses_merge_above;
    const shown = flying.length > lim ? flying.slice(-1) : flying;
    shown.forEach((m, i) => {
      const p = fpos(m.from)!, q = fpos(m.to)!;
      // under collaboration pulses lock to one shared beat: all start together
      const k = ease((now - m.at) / D.travel + (sc.mood.collaboration ? 0 : -0.12 * (i % 3)));
      els.push({ id: `p:${i}`, kind: "pulse", x: p.x + (q.x - p.x) * k, y: p.y + (q.y - p.y) * k, r: flying.length > lim ? 6 : 3, opacity: clamp(1 - k * 0.4) });
    });
  }

  // tethers: a taut line from a waiting figure to the one it waits on
  for (const f of sc.figures) {
    const p = fpos(f.node), q = fpos(f.tether_to);
    if (p && q) els.push({ id: `te:${f.node}`, kind: "tether", x: p.x, y: p.y, x2: q.x, y2: q.y, r: 0, width: 1.5, opacity: 0.8 * fade(`f:${f.node}`) });
  }

  // figures
  const maxTok = Math.max(1, ...sc.figures.filter((f) => live.has(f.node)).map((f) => x.tokens.get(f.node) ?? 0));
  for (const f of sc.figures) {
    const p = fpos(f.node);
    if (!p) continue;
    const id = `f:${f.node}`;
    const alpha = clamp((f.lightness_pct / 100) * light);
    const started = x.started.get(f.node);
    const born = started === undefined ? 1 : reduced ? 1 : ease((now - started) / D.slow); // scale 0 -> 1 (slow)
    const tok = x.tokens.get(f.node) ?? 0;
    const elapsed = started === undefined ? 0 : Math.max(0, now - started);
    const hover = [f.item ?? "", fmt(tok), `${Math.floor(elapsed / 1000)}s`].filter(Boolean);
    if (f.state === "retired") {
      els.push({ id, kind: "rim", x: p.x, y: p.y, r: p.r, shape: f.outcome_mark ?? "no_mark", opacity: alpha * fade(id), hover });
      continue;
    }
    const r = p.r * born;
    const breathing = f.state === "running" || f.state === "continuing" || f.state === "idle";
    // a turn breathes faster as it runs (calm -> tense)
    const quick = 1 + Math.min(elapsed / 60000, 1) * 0.5 * (f.state === "running" ? 1 : 0);
    const halo = reduced || !breathing ? (f.state === "retiring" ? 0 : 1.12) : 1.18 + 0.08 * phase(D.breath / quick / (f.state === "idle" ? 0.5 : 1), f.node.length);
    if (halo > 0) els.push({ id: `ha:${f.node}`, kind: "halo", x: p.x, y: p.y, r: r * halo, opacity: alpha * 0.25 * fade(id) });
    els.push({ id, kind: "figure", x: p.x, y: p.y, r, shape: f.shape, notches: f.notches, width: f.state === "retiring" ? 1 : 2, opacity: alpha * fade(id), hover });
    if (!reduced && f.state === "running") {
      const n = 3 + Math.min(6, Math.floor(tok / 500));
      for (let i = 0; i < n; i++) {
        const a = (2 * Math.PI * i) / n + (tMs * tempo * quick) / 700 + hash(i) * 2;
        const rr = r * (0.25 + 0.4 * hash(i + 17));
        els.push({ id: `in:${f.node}:${i}`, kind: "inner", x: p.x + rr * Math.cos(a), y: p.y + rr * Math.sin(a), r: 1.6, opacity: alpha * 0.8 });
      }
    } else if (!reduced && f.state === "continuing") {
      const a = (tMs * tempo) / 500;
      els.push({ id: `in:${f.node}:0`, kind: "inner", x: p.x + r * 1.3 * Math.cos(a), y: p.y + r * 1.3 * Math.sin(a), r: 2.4, opacity: alpha });
    }
    if (f.ring_shape !== "absent") els.push({ id: `ri:${f.node}`, kind: "ring", x: p.x, y: p.y, r: r + 6, shape: f.ring_shape, width: 2, opacity: alpha * fade(id) });
    if (tok > 0) els.push({ id: `fu:${f.node}`, kind: "fuel", x: p.x, y: p.y, r: r + 11, frac: tok / maxTok, ticks: sc.mood.tension ? 8 : 0, width: 2, opacity: alpha * 0.6 });
  }

  // tiles: waiting = outline, held = outline attached, done = filled, failed = split, dropped = dotted 1 s
  for (const t of sc.tiles) {
    const p = at.get(`t:${t.id}`);
    if (!p) continue;
    els.push({
      id: `t:${t.id}`, kind: "tile", x: p.x, y: p.y, w: TILE_W, h: TILE_H, r: p.r,
      filled: t.shelf === "done", split: t.shelf === "failed", opacity: fade(`t:${t.id}`), hover: [t.id],
    });
  }
  sc.dropped_marks.forEach((id, i) => {
    els.push({ id: `dr:${id}`, kind: "tile", x: b.waiting.x + b.waiting.w - 20 - i * (TILE_W + 8), y: b.waiting.y + b.waiting.h / 2, w: TILE_W, h: TILE_H, r: TILE_W / 2, dotted: true, opacity: 0.8 });
  });

  // words: one per figure, next to it; the sticky stage word in the middle of the stage
  for (const f of sc.figures) {
    const p = fpos(f.node);
    if (!f.word || !p) continue;
    els.push({ id: `w:${f.node}`, kind: "word", text: f.word, x: p.x + p.r + 14, y: p.y - p.r * 0.6, r: 0, opacity: fade(`f:${f.node}`) });
  }
  if (sc.stage_word) {
    els.push({ id: "w:stage", kind: "word", text: sc.stage_word, x: b.stage.x + b.stage.w / 2, y: b.stage.y + 18, r: 0, opacity: 1 });
  }
  return { width: w, height: h, scene: sc, els };
}

/** Topmost element with hover numbers under (px, py), for the tooltip. */
export function hitTest(f: Frame, px: number, py: number): El | null {
  for (let i = f.els.length - 1; i >= 0; i--) {
    const e = f.els[i];
    if (!e.hover) continue;
    if (e.kind === "edge" || e.kind === "horizon") {
      const x2 = e.x2 ?? e.x, y2 = e.y2 ?? e.y;
      const dx = x2 - e.x, dy = y2 - e.y;
      const L = dx * dx + dy * dy || 1;
      const k = Math.max(0, Math.min(1, ((px - e.x) * dx + (py - e.y) * dy) / L));
      if (Math.hypot(e.x + dx * k - px, e.y + dy * k - py) <= Math.max(6, (e.width ?? 1) + 3)) return e;
    } else if (Math.hypot(e.x - px, e.y - py) <= Math.max(e.r, 8)) return e;
  }
  return null;
}

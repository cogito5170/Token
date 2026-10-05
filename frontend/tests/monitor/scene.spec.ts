// CMD-FE2 done_when (pure part): scene == design/golden at each golden t; same events + t = same frame;
// reduced motion moves nothing but opacity; no stage text but the five words.
import { expect, test } from "@playwright/test";
import { encoding } from "../../src/monitor/encoding";
import { draw } from "../../src/monitor/draw";
import { frame, hitTest } from "../../src/monitor/frame";
import { scene } from "../../src/monitor/scene";
import { END, events, goldens, recorder } from "./fixture";

const OPTS = { width: 1280, height: 800, reduced: false };
const RM = { ...OPTS, reduced: true };
const ms = (iso: string) => Date.parse(iso);
const t0 = ms(events[0].observed_at);
const eventTimes = [...new Set(events.map((e) => ms(e.observed_at) - t0))];
const ts = (step: number) => Array.from({ length: END / step + 1 }, (_, i) => i * step);

test.describe("scene vs golden", () => {
  test("there are ten golden scenes", () => {
    expect(goldens.length).toBe(10);
  });
  for (const g of goldens) {
    test(`t=${g.t_ms}`, () => {
      const { recording: _r, ...want } = g;
      expect(scene(events, g.t_ms as number)).toEqual(want);
    });
  }
  test("event order in the input does not matter (seq order)", () => {
    const shuffled = [...events].reverse();
    for (const g of goldens) expect(scene(shuffled, g.t_ms as number)).toEqual(scene(events, g.t_ms as number));
  });
});

test.describe("determinism", () => {
  test("same events + same t give the same frame and the same draw calls", () => {
    for (const t of ts(250)) {
      for (const o of [OPTS, RM]) {
        const a = frame(events, t, o), b = frame([...events], t, o);
        expect(b).toEqual(a);
        const ra = recorder(), rb = recorder();
        draw(ra.ctx, a, "dark"); draw(rb.ctx, b, "dark");
        expect(rb.calls).toEqual(ra.calls);
      }
    }
  });
  test("the frame does change with t (motion exists)", () => {
    expect(frame(events, 4100, OPTS)).not.toEqual(frame(events, 4400, OPTS));
  });
});

type El = ReturnType<typeof frame>["els"][number];
const geometry = (e: El) => {
  const { opacity: _o, hover: _h, ...g } = e;
  return g;
};
/** Ids whose geometry differs between two frames (an id present in only one is not a move). */
function moved(a: El[], b: El[]): string[] {
  const m = new Map(a.map((e) => [e.id, e]));
  return b.filter((e) => m.has(e.id) && JSON.stringify(geometry(m.get(e.id)!)) !== JSON.stringify(geometry(e))).map((e) => e.id);
}

test.describe("reduced motion", () => {
  test("between frames nothing moves; only opacity changes", () => {
    const steps = ts(16);
    for (let i = 1; i < steps.length; i++) {
      const a = frame(events, steps[i - 1], RM), b = frame(events, steps[i], RM);
      const changed = eventTimes.some((et) => et > steps[i - 1] && et <= steps[i]);
      if (changed) continue; // a new state swaps shapes instantly (motion.md 6)
      expect(moved(a.els, b.els), `t=${steps[i]}`).toEqual([]);
    }
  });
  test("state swaps are instant: the frame right after an event already has its resting geometry", () => {
    for (const et of eventTimes) {
      const a = frame(events, et, RM), b = frame(events, et + 500, RM);
      expect(moved(a.els, b.els), `t=${et}`).toEqual([]);
    }
  });
  test("no particles, pulses, inner dots or breathing", () => {
    for (const t of ts(100)) {
      const kinds = new Set(frame(events, t, RM).els.map((e) => e.kind));
      for (const k of ["dust", "pulse", "inner"]) expect(kinds.has(k as El["kind"])).toBe(false);
    }
  });
  test("fades last at most max_fade_ms", () => {
    const fade = encoding.reduced_motion.max_fade_ms;
    for (const et of eventTimes) {
      const a = frame(events, et + fade, RM), b = frame(events, et + fade + 300, RM);
      const later = eventTimes.some((x) => x > et && x <= et + fade + 300);
      if (later) continue;
      const op = new Map(a.els.map((e) => [e.id, e.opacity]));
      const holds = (id: string) => id.startsWith("e:"); // a message highlight holds highlight_hold_ms
      for (const e of b.els) if (op.has(e.id) && !holds(e.id)) expect(e.opacity, `${e.id} t=${et}`).toBeCloseTo(op.get(e.id)!, 6);
    }
  });
  test("full motion does move things (the check above is not vacuous)", () => {
    const a = frame(events, 4100, OPTS), b = frame(events, 4116, OPTS);
    expect(moved(a.els, b.els).length).toBeGreaterThan(0);
  });
});

test.describe("words", () => {
  const allowed = new Set(encoding.words);
  test("only the five words are ever drawn on stage", () => {
    const drawn = new Set<string>();
    for (const t of ts(100)) {
      for (const o of [OPTS, RM]) {
        for (const theme of ["dark", "light"] as const) {
          const r = recorder();
          draw(r.ctx, frame(events, t, o), theme);
          for (const [k, a] of r.calls) {
            if (k === "strokeText") drawn.add(`stroke:${a[0]}`);
            if (k === "fillText") drawn.add(String(a[0]));
          }
        }
      }
    }
    expect(drawn.size).toBeGreaterThan(0);
    for (const w of drawn) expect(allowed.has(w), w).toBe(true);
  });
  test("drawn words are exactly the scene words, one per figure", () => {
    for (const t of ts(250)) {
      const f = frame(events, t, OPTS);
      const r = recorder();
      draw(r.ctx, f, "dark");
      const drawn = r.calls.filter(([k]) => k === "fillText").map(([, a]) => String(a[0]));
      const want = [...f.scene.figures.map((x) => x.word).filter(Boolean), ...(f.scene.stage_word ? [f.scene.stage_word] : [])];
      expect(drawn.sort()).toEqual((want as string[]).sort());
    }
  });
  test("a word outside the five never reaches the canvas", () => {
    const f = frame(events, 4000, OPTS);
    f.els.push({ id: "w:x", kind: "word", text: "token", x: 1, y: 1, r: 0, opacity: 1 });
    const r = recorder();
    draw(r.ctx, f, "dark");
    expect(r.calls.filter(([k, a]) => k === "fillText" && a[0] === "token")).toEqual([]);
  });
  test("numbers live only in hover", () => {
    const f = frame(events, 5000, OPTS);
    const fig = f.els.find((e) => e.kind === "figure")!;
    const hit = hitTest(f, fig.x, fig.y);
    expect(hit?.hover?.some((l) => /\d/.test(l))).toBe(true);
    for (const e of f.els) if (e.kind === "word") expect(e.text).toMatch(/^[a-z]+$/);
  });
});

test.describe("encoding", () => {
  test("figure size stays within 24–72 px diameter", () => {
    for (const t of ts(250)) for (const e of frame(events, t, RM).els) if (e.kind === "figure") {
      expect(e.r * 2).toBeGreaterThanOrEqual(24 - 1e-9);
      expect(e.r * 2).toBeLessThanOrEqual(72 + 1e-9);
    }
  });
  test("edge stroke width is the golden weight", () => {
    const f = frame(events, 5000, OPTS);
    const e = f.els.find((x) => x.kind === "edge")!;
    expect(e.width).toBe(f.scene.edges[0].weight_px);
  });
  test("particles stay under the limit", () => {
    for (const t of ts(500)) expect(frame(events, t, OPTS).els.filter((e) => e.kind === "dust").length).toBeLessThanOrEqual(encoding.limits.particles_max);
  });
});

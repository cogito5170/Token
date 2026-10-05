// CMD-FE3 S4: a failed judge (node.state.done status=failed, or queue.failed) is visible on the stage; green clears it.
import { describe, expect, it } from "vitest";
import { frame } from "../../src/monitor/frame";
import { scene } from "../../src/monitor/scene";
import type { MonitorEvent } from "../../src/monitor/types";

const at = (s: number) => `2026-01-01T00:00:${String(s).padStart(2, "0")}.000Z`;
let seq = 0;
const ev = (s: number, kind: string, extra: Partial<MonitorEvent> = {}): MonitorEvent => ({ seq: ++seq, kind, observed_at: at(s), provenance: "OBSERVED", data: {}, ...extra });

const base = (): MonitorEvent[] => {
  seq = 0;
  return [
    ev(0, "file:pool.round", { data: { roles: ["judge"], round: 1 } }),
    ev(0, "file:queue.added", { item: "w5", role: "judge", data: { id: "w5", parent: null } }),
    ev(1, "file:pool.live.claimed", { node: "n1", role: "judge", item: "w5", data: {} }),
  ];
};
const red = (s: number) => [
  ev(s, "file:node.state.done", { node: "n1", item: "w5", data: { status: "failed", verified: false } }),
  ev(s, "file:queue.failed", { item: "w5", role: "judge", data: { id: "w5", parent: null } }),
];
const green = (s: number) => [ev(s, "file:node.state.done", { node: "n1", item: "w7", data: { status: "done", verified: true } })];
const OPTS = { width: 1280, height: 800, reduced: false };
const ring = (evs: MonitorEvent[], t: number) => frame(evs, t, OPTS).els.find((e) => e.kind === "ring" && e.id === "ri:n1");

describe("failed judge signal", () => {
  it("scene: failed status gives the failed ring (jagged gap) and a failed-shelf tile", () => {
    const sc = scene([...base(), ...red(5)], 6000);
    const fig = sc.figures.find((f) => f.node === "n1")!;
    expect(fig.ring).toBe("failed");
    expect(fig.ring_shape).toBe("jagged_gap");
    expect(sc.tiles.find((t) => t.id === "w5")!.shelf).toBe("failed");
  });
  it("scene: before the failure there is no ring; a later green result clears it", () => {
    expect(scene(base(), 3000).figures[0].ring).toBe("none");
    const evs = [...base(), ...red(5), ...green(9)];
    expect(scene(evs, 6000).figures[0].ring_shape).toBe("jagged_gap");
    expect(scene(evs, 10000).figures[0].ring).toBe("verified");
    expect(scene(evs, 10000).figures[0].ring_shape).not.toBe("jagged_gap");
  });
  it("frame: the failed ring is drawn as a jagged_gap ring element and is gone after green", () => {
    const evs = [...base(), ...red(5), ...green(9)];
    expect(ring(evs, 6000)?.shape).toBe("jagged_gap");
    expect(ring(evs, 10000)?.shape).toBe("closed");
    expect(ring(base(), 3000)).toBeUndefined();
    const tile = (e: MonitorEvent[], t: number) => frame(e, t, OPTS).els.find((x) => x.id === "t:w5");
    expect(tile(evs, 6000)?.split).toBe(true);
    expect(tile(base(), 3000)?.split).toBeFalsy();
  });
});

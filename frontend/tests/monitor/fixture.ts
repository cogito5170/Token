// Shared test inputs: the CMD-RN1 fixture recording, the CMD-DS3 golden scenes, a recording Ctx.
import { readdirSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { parseRecording } from "../../src/monitor/feed";
import type { Ctx } from "../../src/monitor/draw";

export const repo = join(dirname(fileURLToPath(import.meta.url)), "../../..");
export const events = parseRecording(readFileSync(join(repo, "fixtures/monitor/recording.jsonl"), "utf8"));
export const goldens = readdirSync(join(repo, "design/golden"))
  .filter((n) => /^t\d+\.json$/.test(n))
  .sort()
  .map((n) => JSON.parse(readFileSync(join(repo, "design/golden", n), "utf8")) as Record<string, unknown>);
export const END = 12000;

/** A Canvas 2D stand-in that records every call and property write. */
export function recorder(): { ctx: Ctx; calls: [string, unknown[]][] } {
  const calls: [string, unknown[]][] = [];
  const ctx = new Proxy({} as Record<string, unknown>, {
    get: (o, k: string) => (k in o ? o[k] : (...a: unknown[]) => { calls.push([k, a]); }),
    set: (o, k: string, v) => { calls.push([`=${k}`, [v]]); o[k] = v; return true; },
  });
  return { ctx: ctx as unknown as Ctx, calls };
}

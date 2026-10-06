// Acceptance test for CMD-TKG9 (written by baseline; the executor may not edit it).
import { describe, expect, it } from "vitest";
import { execFileSync } from "node:child_process";
import { resolve } from "node:path";
import { createFakeFetch } from "../../src/lib/api/fake";

const report = { id: "r1", period: { from: "2026-09-01", to: "2026-09-30" }, body: { usage: {} } };

describe("createFakeFetch wrapper detection (CMD-TKG9)", () => {
  it("returns an object that merely has a body field as a whole", async () => {
    const f = createFakeFetch({ "GET /v1/tkg9": () => report });
    const r = await f.fetch("http://x/v1/tkg9");
    expect(r.status).toBe(200);
    expect(await r.json()).toEqual(report);
  });
  it("still unwraps real {status, body} wrappers", async () => {
    const f = createFakeFetch({ "GET /v1/tkg9a": () => ({ status: 201, body: { ok: 1 } }), "GET /v1/tkg9b": () => ({ status: 204 }) });
    const a = await f.fetch("http://x/v1/tkg9a");
    expect(a.status).toBe(201);
    expect(await a.json()).toEqual({ ok: 1 });
    expect((await f.fetch("http://x/v1/tkg9b")).status).toBe(204);
  });
  it("the frontend still type-checks (tsc)", () => {
    execFileSync("npx", ["tsc", "--noEmit", "-p", "tsconfig.json"], { cwd: resolve(__dirname, "../.."), stdio: "pipe" });
  }, 120_000);
});

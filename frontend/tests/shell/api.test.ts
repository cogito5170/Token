import { describe, expect, it } from "vitest";
import { execFileSync } from "node:child_process";
import { resolve } from "node:path";
import { createClient, ApiError } from "../../src/lib/api/client";
import { createFakeFetch } from "../../src/lib/api/fake";
import { outputs } from "../../src/lib/gen/run.mjs";
import { readFileSync } from "node:fs";

const fe = resolve(__dirname, "../..");

describe("typed client", () => {
  it("generated schema is in sync with docs/api/openapi.yaml", async () => {
    const out = await outputs();
    for (const [p, c] of Object.entries(out)) expect(readFileSync(resolve(fe, p), "utf8"), p).toBe(c);
  });

  it("client types compile (tsc)", () => {
    execFileSync("npx", ["tsc", "--noEmit", "-p", "tsconfig.json"], { cwd: fe, stdio: "pipe" });
  }, 120_000);

  it("calls typed paths through the fake API and records them", async () => {
    const fake = createFakeFetch();
    const c = createClient({ baseUrl: "http://x", fetch: fake.fetch, getToken: () => "t" });
    const ws = await c.get("/v1/workspaces");
    expect(ws[0].role).toBe("admin");
    const s = await c.get("/v1/workspaces/{ws}/usage/summary", { params: { ws: ws[0].id }, query: { from: "2026-09-01T00:00:00Z" } });
    expect(s.tiles.cost_cli.value).toBeNull();
    expect(fake.calls.map((x) => x.path)).toEqual(["/v1/workspaces", `/v1/workspaces/${ws[0].id}/usage/summary`]);
    expect(fake.calls[1].query.from).toBe("2026-09-01T00:00:00Z");
  });

  it("surfaces API errors", async () => {
    const c = createClient({ baseUrl: "http://x", fetch: createFakeFetch().fetch });
    await expect(c.get("/v1/models")).rejects.toBeInstanceOf(ApiError);
  });
});

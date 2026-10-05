// Acceptance test for CMD-AGA4 (written by baseline; the executor may not edit it).
import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { execFileSync } from "node:child_process";
import { listReports, generateReport, exportReport, exportCsv, reportFileName } from "../../src/app/(app)/reports/load";

const calls: unknown[][] = [];
const client: any = {
  get: (p: string, o: unknown) => { calls.push(["get", p, o]); return Promise.resolve([]); },
  post: (p: string, o: unknown) => { calls.push(["post", p, o]); return Promise.resolve({ id: "r1", period: { from: "a", to: "b" }, body: {} }); },
};

describe("reports load", () => {
  it("lists reports", async () => {
    calls.length = 0;
    await listReports(client, "w1");
    expect(calls[0]).toEqual(["get", "/v1/workspaces/{ws}/reports", { params: { ws: "w1" } }]);
  });
  it("generates a report for a period", async () => {
    calls.length = 0;
    await generateReport(client, "w1", { from: "2026-09-01", to: "2026-09-30" });
    expect(calls[0]).toEqual(["post", "/v1/workspaces/{ws}/reports", { params: { ws: "w1" }, body: { from: "2026-09-01", to: "2026-09-30" } }]);
  });
  it("exports JSON through the client", async () => {
    calls.length = 0;
    await exportReport(client, "w1", "r1");
    expect(calls[0]).toEqual(["get", "/v1/workspaces/{ws}/reports/{report}/export", { params: { ws: "w1", report: "r1" }, query: { format: "json" } }]);
  });
  it("exports CSV as text with the bearer token", async () => {
    const seen: any[] = [];
    const f = async (url: string, init?: RequestInit) => { seen.push([url, init]); return new Response("a,b\n1,2\n", { status: 200 }); };
    const text = await exportCsv(f, "http://api", "tok-fake", "w1", "r 1");
    expect(text).toBe("a,b\n1,2\n");
    expect(seen[0][0]).toBe("http://api/v1/workspaces/w1/reports/r%201/export?format=csv");
    expect((seen[0][1].headers as Record<string, string>).authorization).toBe("Bearer tok-fake");
    const bad = async () => new Response("no", { status: 404 });
    await expect(exportCsv(bad, "http://api", "t", "w1", "r1")).rejects.toThrow();
  });
  it("names the downloaded file after the period", () => {
    expect(reportFileName({ id: "r1", period: { from: "2026-09-01", to: "2026-09-30" }, body: {} } as any, "csv")).toBe("report-2026-09-01_2026-09-30.csv");
  });
  it("is in the nav under 컨설팅", () => {
    const nav = JSON.parse(readFileSync(resolve(__dirname, "../../src/app/(app)/reports/nav.json"), "utf8"));
    expect(nav).toEqual({ group: "consulting", label: "리포트", order: 90 });
  });
  it("has a page", async () => {
    const page = await import("../../src/app/(app)/reports/page");
    expect(typeof page.default).toBe("function");
  });
  it("type-checks (the page must build)", () => {
    const root = resolve(__dirname, "../..");
    let out = "";
    try { execFileSync(process.execPath, [resolve(root, "node_modules/typescript/bin/tsc"), "--noEmit", "-p", root], { encoding: "utf8" }); }
    catch (e: any) { out = String(e.stdout || e.message); }
    expect(out).toBe("");
  }, 120_000);
});

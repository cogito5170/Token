// Acceptance test for CMD-AGA5 (written by baseline; the executor may not edit it).
import { beforeAll, describe, expect, it } from "vitest";
import * as React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { execFileSync } from "node:child_process";
import { resolve } from "node:path";

const h = React.createElement;
let m: any;
beforeAll(async () => {
  (globalThis as { React?: unknown }).React = React;
  m = await import("../../src/app/(app)/reports/ReportsView");
});
const rep = (id: string, from: string, to: string, created_at?: string) => ({ id, period: { from, to }, body: {}, created_at });
const html = (reports: unknown[]) => renderToStaticMarkup(h(m.ReportsView, { reports, onGenerate() {}, onExport() {} })).replace(/<!-- -->/g, "");

describe("ReportsView follows the screens' grammar", () => {
  it("is a gc-screen main with data-screen=reports", () => {
    expect(html([])).toMatch(/^<main class="gc-screen" data-screen="reports">/);
  });
  it("labels the period inputs 시작 and 끝 (no English labels)", () => {
    const out = html([]);
    expect(out).toContain('<form class="gc-form"');
    expect(out).toMatch(/<label>시작<input[^>]*name="from"/);
    expect(out).toMatch(/<label>끝<input[^>]*name="to"/);
    expect(out).not.toMatch(/From:|To:/);
  });
  it("shows the empty state as gc-empty", () => {
    expect(html([])).toContain('<p class="gc-empty">리포트가 없다.</p>');
  });
  it("uses a gc-table with Korean headers and a readable created time", () => {
    const out = html([rep("a1", "2026-09-01", "2026-09-30", "2026-10-05T13:58:16.003067+00:00"), rep("b2", "2026-10-01", "2026-10-05")]);
    expect(out).toContain('<table class="gc-table num" aria-label="리포트 목록">');
    expect(out).toContain("<th>기간</th><th>만든 때</th><th>내보내기</th>");
    expect(out).toContain("<td>2026-10-05 13:58</td>");
    expect(out).toContain("<td>—</td>");
    expect(out).not.toContain("T13:58:16");
  });
  it("names each export button by its format and period", () => {
    const out = html([rep("a1", "2026-09-01", "2026-09-30")]);
    expect(out).toContain('aria-label="CSV 내려받기 2026-09-01 ~ 2026-09-30"');
    expect(out).toContain('aria-label="JSON 내려받기 2026-09-01 ~ 2026-09-30"');
  });
  it("type-checks (the page must build)", () => {
    const root = resolve(__dirname, "../..");
    let out = "";
    try { execFileSync(process.execPath, [resolve(root, "node_modules/typescript/bin/tsc"), "--noEmit", "-p", root], { encoding: "utf8" }); }
    catch (e: any) { out = String(e.stdout || e.message); }
    expect(out).toBe("");
  }, 120_000);
});

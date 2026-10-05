// Acceptance test for CMD-AGA2 (written by baseline; the executor may not edit it).
import { beforeAll, describe, expect, it } from "vitest";
import * as React from "react";
import { renderToStaticMarkup } from "react-dom/server";

const h = React.createElement;
let m: any;
beforeAll(async () => {
  (globalThis as { React?: unknown }).React = React;
  m = await import("../../src/app/(app)/reports/ReportsView");
});
const rep = (id: string, from: string, to: string) => ({ id, period: { from, to }, body: {}, created_at: "2026-10-05T00:00:00Z" });
const html = (reports: unknown[]) => renderToStaticMarkup(h(m.ReportsView, { reports, onGenerate() {}, onExport() {} }));
const both = (a: string, b: string) => new RegExp(`<[^>]*${a}[^>]*${b}|<[^>]*${b}[^>]*${a}`);

describe("ReportsView", () => {
  it("is titled 리포트 and shows it as h1", () => {
    expect(m.TITLE).toBe("리포트");
    expect(html([])).toContain("<h1>리포트</h1>");
  });
  it("says so when there is no report", () => {
    expect(html([])).toContain("리포트가 없다.");
  });
  it("lists one row per report with its period and a CSV and a JSON export button", () => {
    const out = html([rep("a1", "2026-09-01", "2026-09-30"), rep("b2", "2026-10-01", "2026-10-05")]);
    expect(out.replace(/<!-- -->/g, "")).toContain("2026-09-01 ~ 2026-09-30");
    expect(out.replace(/<!-- -->/g, "")).toContain("2026-10-01 ~ 2026-10-05");
    expect((out.match(/<tbody[\s\S]*<\/tbody>/)?.[0].match(/<tr/g) ?? []).length).toBe(2);
    for (const id of ["a1", "b2"]) for (const f of ["csv", "json"]) expect(out).toMatch(both(`data-report-id="${id}"`, `data-export="${f}"`));
  });
  it("has a period form: two date inputs named from and to, and a 생성 submit button", () => {
    const out = html([]);
    expect(out).toMatch(both('name="from"', 'type="date"'));
    expect(out).toMatch(both('name="to"', 'type="date"'));
    expect(out).toMatch(/<button[^>]*type="submit"[^>]*>생성<\/button>/);
  });
});

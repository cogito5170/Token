import { describe, expect, it } from "vitest";
import React, { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { createClient, createFakeFetch, fixtures } from "../../src/lib/api";
import type { Schemas } from "../../src/lib/api";
import { loadOverview, budgetUsePermille } from "../../src/app/(app)/overview/load";
import { trendOption } from "../../src/app/(app)/overview/trend";
import { OverviewView } from "../../src/app/(app)/overview/View";
import { loadTokenMix, mixShares, byModel } from "../../src/app/(app)/token-mix/load";
import { mixOption } from "../../src/app/(app)/token-mix/options";
import { loadCallSize, loadOutlierCalls, binPercentile } from "../../src/app/(app)/call-size/load";
import { CallSizeView } from "../../src/app/(app)/call-size/View";

// Screens use the automatic JSX runtime under Next; vitest here compiles classic JSX.
(globalThis as { React?: unknown }).React = React;

const WS = fixtures.workspace.id;
const P = `/v1/workspaces/${WS}`;
const ser = (name: string, vals: number[], unit: Schemas["Unit"] = "tokens", provenance: Schemas["Provenance"] = "MEASURED"): Schemas["Series"] =>
  ({ name, unit, provenance, points: vals.map((v, i) => [`2026-09-0${i + 1}`, v]) });
const hist: Schemas["Histogram"] = {
  unit: "tokens", provenance: "CALCULATED", threshold: 50_000,
  bins: [{ lo: 1024, hi: 2048, count: 6 }, { lo: 2048, hi: 4096, count: 3 }, { lo: 4096, hi: 8192, count: 1 }],
  outliers: [{ call_id: 7, context_tokens: 60_000, model_id: "m1" }],
};
const setup = (extra = {}) => {
  const fake = createFakeFetch(extra);
  return { fake, client: createClient({ baseUrl: "http://x", fetch: fake.fetch }) };
};

describe("overview", () => {
  it("calls only /usage/summary and /budgets", async () => {
    const { fake, client } = setup({ [`GET /v1/workspaces/{ws}/budgets`]: () => [] });
    await loadOverview(client, WS);
    expect(fake.calls.map((c) => c.path).sort()).toEqual([`${P}/budgets`, `${P}/usage/summary`]);
  });
  it("shows both cost measures side by side with the partial cli chip below 100%", async () => {
    const { client } = setup({ [`GET /v1/workspaces/{ws}/budgets`]: () => [] });
    const html = renderToStaticMarkup(createElement(OverviewView, { data: await loadOverview(client, WS) }));
    expect(html).toContain("API 정가 환산");
    expect(html).toContain("CLI 비용");
    expect(html).toContain("$0.0012");
    expect(html).toContain("부분 0%");
    expect(html).toContain("41.2%"); // budget_use tile fallback
  });
  it("no partial chip at 100% coverage; unknown cli is a dash, not 0", () => {
    const s = structuredClone(fixtures.usageSummary) as Schemas["UsageSummary"];
    s.tiles.cost_cli = { value: 5000, unit: "microusd", provenance: "MEASURED", coverage_permille: 1000 };
    const html = renderToStaticMarkup(createElement(OverviewView, { data: { summary: s, budgets: [] } }));
    expect(html).not.toContain("부분");
    expect(html).toContain("$0.0050");
    expect(html).toContain("—"); // cost_cli_per_correct null
  });
  it("budget use comes from the workspace/month budget when present", () => {
    const m = (v: number | null): Schemas["Metric"] => ({ value: v, unit: "microusd", provenance: "CALCULATED" });
    const b = { id: "b", scope: "workspace", period: "month", measure: "list", limit_microusd: 2000, thresholds: [], used: { list: m(500), cli: m(null) } } as Schemas["Budget"];
    expect(budgetUsePermille({ summary: fixtures.usageSummary, budgets: [b] }).value).toBe(250);
  });
  it("pins the provenance chip of every overview tile", async () => {
    const { client } = setup({ [`GET /v1/workspaces/{ws}/budgets`]: () => [] });
    const html = renderToStaticMarkup(createElement(OverviewView, { data: await loadOverview(client, WS) }));
    const chips = (label: string) => {
      const m = new RegExp(`<section class="gc-kpi" aria-label="${label}">.*?</section>`).exec(html);
      expect(m, label).not.toBeNull();
      return [...m![0].matchAll(/data-provenance="(\w+)"/g)].map((x) => x[1]);
    };
    expect(chips("총 토큰")).toEqual(["MEASURED"]);
    expect(chips("비용")).toEqual(["CALCULATED", "MEASURED"]);
    expect(chips("맞힌 작업 수")).toEqual(["MEASURED"]);
    expect(chips("맞힌 작업당 비용")).toEqual(["CALCULATED"]);
    expect(chips("예산 사용률")).toEqual(["CALCULATED"]);
  });
  it("budget use stays CALCULATED, from a budget or from the tile", () => {
    const m = (v: number | null): Schemas["Metric"] => ({ value: v, unit: "microusd", provenance: "CALCULATED" });
    const b = { id: "b", scope: "workspace", period: "month", measure: "list", limit_microusd: 2000, thresholds: [], used: { list: m(500), cli: m(null) } } as Schemas["Budget"];
    expect(budgetUsePermille({ summary: fixtures.usageSummary, budgets: [b] }).provenance).toBe("CALCULATED");
    expect(budgetUsePermille({ summary: fixtures.usageSummary, budgets: [] }).provenance).toBe("CALCULATED");
  });
  it("trend plots total_tokens, cost_list, cost_cli with cli on the cost axis", () => {
    const o = trendOption([ser("total_tokens", [1, 2]), ser("cost_list", [3, 4], "microusd", "CALCULATED"), ser("cost_cli", [3, 4], "microusd"), ser("other", [1, 1])]) as { series: { name: string; yAxisIndex: number }[] };
    expect(o.series.map((s) => [s.name, s.yAxisIndex])).toEqual([["토큰", 0], ["비용(정가)", 1], ["비용(CLI)", 1]]);
  });
});

describe("token_mix", () => {
  it("calls only /usage/series/tokens, group_by follows the toggle", async () => {
    const { fake, client } = setup({ "GET /v1/workspaces/{ws}/usage/series/tokens": () => ({ bucket: "day", series: [] }) });
    await loadTokenMix(client, WS, "none");
    await loadTokenMix(client, WS, "model");
    expect(fake.calls.map((c) => [c.path, c.query.group_by])).toEqual([[`${P}/usage/series/tokens`, "none"], [`${P}/usage/series/tokens`, "model"]]);
  });
  const set = { bucket: "day", series: [ser("input", [40]), ser("cache_read", [40]), ser("cache_write", [10]), ser("output", [10])] };
  it("computes shares and a 4-layer stacked area", () => {
    expect(mixShares(set)).toEqual({ input: 400, cache_read: 400, cache_write: 100, output: 100 });
    const o = mixOption(set.series) as { series: { stack: string; name: string }[] };
    expect(o.series.map((s) => s.name)).toEqual(["입력", "캐시 읽기", "캐시 쓰기", "출력"]);
    expect(new Set(o.series.map((s) => s.stack)).size).toBe(1);
  });
  it("splits model-prefixed series", () => {
    const m = byModel({ bucket: "day", series: [ser("a:input", [1]), ser("a:output", [1]), ser("b:input", [1])] });
    expect([...m.keys()]).toEqual(["a", "b"]);
    expect(mixShares({ bucket: "day", series: [] }).input).toBeNull();
  });
});

describe("call_size", () => {
  const handlers = {
    "GET /v1/workspaces/{ws}/usage/series/call-size": () => hist,
    "GET /v1/workspaces/{ws}/usage/calls": () => ({ items: [{ id: 7, occurred_at: "2026-09-01T00:00:00Z", model_id: "m1", provider: "p", source_kind: "api_proxy", context_tokens: 60_000 }] }),
  };
  it("calls only call-size, and calls with min_input=threshold on demand", async () => {
    const { fake, client } = setup(handlers);
    await loadCallSize(client, WS);
    expect(fake.calls.map((c) => c.path)).toEqual([`${P}/usage/series/call-size`]);
    const page = await loadOutlierCalls(client, WS, hist.threshold);
    expect(fake.calls[1]).toMatchObject({ path: `${P}/usage/calls`, query: { min_input: "50000" } });
    const html = renderToStaticMarkup(createElement(CallSizeView, { hist, calls: page, onOpenOutliers: () => {} }));
    expect(html).toContain("50K 초과 호출 1 건");
    expect(html).toContain("60,000");
  });
  it("percentiles from bins", () => {
    expect(binPercentile(hist.bins, 500)).toBe(1024 + Math.round((1024 * 5) / 6));
    expect(binPercentile([], 500)).toBeNull();
  });
});

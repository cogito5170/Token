import { beforeAll, describe, expect, it } from "vitest";
import * as React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { createClient } from "../../src/lib/api/client";
import { createFakeFetch } from "../../src/lib/api/fake";
import type { Schemas } from "../../src/lib/api";

const A = "../../src/app/(app)";
type M = Record<string, any>;
let compare: M, burn: M, advisor: M, estimate: M, whatif: M, profile: M;
const html = (el: React.ReactElement) => renderToStaticMarkup(el);
const h = React.createElement;

beforeAll(async () => {
  (globalThis as { React?: unknown }).React = React; // shared components use the classic JSX runtime under vitest
  compare = await import(`${A}/compare/CompareView`);
  burn = await import(`${A}/budgets/BurnView`);
  advisor = await import(`${A}/advisor/AdvisorView`);
  estimate = await import(`${A}/estimate/EstimateView`);
  whatif = await import(`${A}/what-if/WhatIfView`);
  profile = await import(`${A}/profile/ProfileView`);
});

const range = (p10: number, p50: number, p90: number, unit: Schemas["Unit"], provenance: Schemas["Provenance"]): Schemas["Range"] => ({ p10, p50, p90, unit, provenance });
const metric = (value: number | null, unit: Schemas["Unit"], provenance: Schemas["Provenance"]): Schemas["Metric"] => ({ value, unit, provenance });

describe("titles are the visualization.md questions", () => {
  const doc = require("node:fs").readFileSync(require("node:path").resolve(__dirname, "../../../docs/visualization.md"), "utf8") as string;
  it.each([
    ["compare", () => compare.TITLE], ["budgets", () => burn.TITLE],
  ])("%s", (_n, t) => { expect(doc).toContain(t()); });
  it("every screen renders its title as h1", () => {
    expect(html(h(estimate.EstimateView, { onSubmit() {} }))).toContain(`<h1>${estimate.TITLE}</h1>`);
    expect(html(h(whatif.WhatIfView, { onSubmit() {} }))).toContain(`<h1>${whatif.TITLE}</h1>`);
  });
});

describe("config_compare", () => {
  it("shows ranges, CALCULATED, and an ESTIMATED recommendation banner", () => {
    const out = html(h(compare.CompareView, {
      data: { dims: ["model"], groups: [{ key: { model: "m1" }, tasks: 5, correct: 4, accuracy: metric(800, "permille", "CALCULATED"), tokens_per_correct: range(100, 200, 300, "tokens", "CALCULATED"), cost_list_per_correct: range(1000, 2000, 3000, "microusd", "CALCULATED") }] },
      recommendations: [{ id: "r1", headline: "m2 로 바꾸면 절감", current_config: {}, recommended_config: {}, saving: metric(500, "microusd", "ESTIMATED"), evidence_n: 7 }],
    }));
    expect(out).toContain("80%");
    expect(out).toContain("$0.0020");
    expect(out).toContain('data-provenance="ESTIMATED"');
    expect(out).toContain("근거 7 건");
  });
});

describe("budget_burn", () => {
  const s = (name: string, pts: [string, number][], provenance: Schemas["Provenance"]): Schemas["Series"] => ({ name, unit: "microusd", provenance, points: pts });
  const b: Schemas["BurnSeries"] = {
    budget_id: "b", limit_microusd: 1000,
    cumulative: { list: s("list", [["2026-09-01", 100], ["2026-09-02", 300]], "CALCULATED"), cli: s("cli", [["2026-09-01", 90], ["2026-09-02", 280]], "MEASURED") },
    projection: { p10: s("p10", [["2026-09-02", 300], ["2026-09-03", 600]], "ESTIMATED"), p50: s("p50", [["2026-09-02", 300], ["2026-09-03", 800]], "ESTIMATED"), p90: s("p90", [["2026-09-02", 300], ["2026-09-03", 1000]], "ESTIMATED"), exhaust_at_p50: "2026-09-10T00:00:00Z" },
  };
  it("draws the projection dashed with a band, thresholds and exhaust date", () => {
    const out = html(h(burn.BurnView, { burn: b }));
    expect(out).toMatch(/data-series="projection-p50"[^>]*stroke-dasharray="6 4"/);
    expect(out).toContain('data-series="projection-band"');
    for (const t of [50, 80, 100]) expect(out).toContain(`data-threshold="${t}"`);
    expect(out).toContain("2026-09-10");
  });
});

describe("estimate", () => {
  const e: Schemas["Estimate"] = {
    id: "e", input_tokens: range(100, 200, 400, "tokens", "ESTIMATED"), cache_tokens: range(0, 10, 20, "tokens", "ESTIMATED"), output_tokens: range(10, 20, 40, "tokens", "ESTIMATED"),
    cost_list: range(1000, 2000, 4000, "microusd", "ESTIMATED"), calls: range(2, 4, 8, "calls", "ESTIMATED"), success_prob: metric(700, "permille", "ESTIMATED"),
    evidence: { n: 12, task_ids: [], basis: "workspace" }, estimator: { version: 3, mape_permille: 180 },
  };
  it("draws ESTIMATED ranges as dashed bands with evidence and the estimator's MAPE", () => {
    const out = html(h(estimate.EstimateView, { result: e, onSubmit() {}, accuracy: { n: 30, mape_tokens: metric(210, "permille", "CALCULATED"), mape_cost: metric(190, "permille", "CALCULATED"), coverage_p10_p90: metric(790, "permille", "CALCULATED"), series: { bucket: "day", series: [] } } }));
    expect(out).toContain('data-kind="ESTIMATED"');
    expect(out).toContain("P10 100");
    expect(out).toContain("근거 12 건");
    expect(out).toContain("v3");
    expect(out).toContain("18%");
    expect(out).toContain('data-testid="self-mape"');
    expect(out).toContain("21%");
  });
  it("posts an estimate through the typed client", async () => {
    const fake = createFakeFetch({ "POST /v1/workspaces/{ws}/estimates": () => ({ status: 201, body: e }) });
    const c = createClient({ baseUrl: "http://x", fetch: fake.fetch });
    const r = await c.post("/v1/workspaces/{ws}/estimates", { params: { ws: "w" }, body: { description: "d", task_kind: "bug", model: "m" } });
    expect(r.estimator.version).toBe(3);
    expect(fake.calls[0].path).toBe("/v1/workspaces/w/estimates");
  });
});

describe("what-if", () => {
  it("shows SIMULATED with its assumption list and a dotted band", () => {
    const sim: Schemas["Simulation"] = {
      id: "s", assumptions: [{ kind: "model_swap", from: "big", value: "small" }, { kind: "context_cap", value: 50000 }],
      basis: { from: "2026-09-01T00:00:00Z", to: "2026-09-30T00:00:00Z", calls: 100, tasks: 10, price_version: 2 },
      result: { baseline: { cost_list: metric(5000, "microusd", "CALCULATED") }, simulated: { cost_list: range(1000, 2000, 3000, "microusd", "SIMULATED") } },
    };
    const out = html(h(whatif.WhatIfView, { result: sim, onSubmit() {} }));
    expect(out).toContain('aria-label="가정 목록"');
    expect(out).toContain("model_swap");
    expect(out).toContain("big");
    expect(out).toContain("context_cap");
    expect(out).toContain('data-kind="SIMULATED"');
    expect(out).toContain('data-provenance="SIMULATED"');
  });
});

describe("advisor: apply requires an explicit confirm step", () => {
  const prop = (state: Schemas["Proposal"]["state"]): Schemas["Proposal"] => ({ id: "p1", origin: "advisor", origin_ref: "f", kind: "context_cap", change: {}, state });
  it("apply button only asks; the dialog appears only after it, and confirm is what applies", () => {
    const base = { findings: [], proposals: [prop("accepted")] };
    expect(html(h(advisor.AdvisorView, base))).not.toContain('role="dialog"');
    const open = html(h(advisor.AdvisorView, { ...base, confirmId: "p1" }));
    expect(open).toContain('role="dialog"');
    expect(open).toContain('data-action="confirm-apply"');
  });
  it("decideProposal refuses apply without confirm and sends confirm:true with it", async () => {
    const sent: unknown[] = [];
    const post = async (b: unknown) => { sent.push(b); return prop("applied"); };
    await expect(advisor.decideProposal(post, "apply", false)).rejects.toThrow(/confirm/);
    expect(sent).toHaveLength(0);
    await advisor.decideProposal(post, "apply", true);
    expect(sent).toEqual([{ decision: "apply", confirm: true }]);
    await advisor.decideProposal(post, "accept", false);
    expect(sent[1]).toEqual({ decision: "accept" });
  });
  it("lists findings as ESTIMATED savings", () => {
    const f: Schemas["Finding"] = { id: "f", rule_id: "R1", period: { from: "2026-09-01", to: "2026-09-30" }, savings: range(1, 2, 3, "microusd", "ESTIMATED"), savings_tokens: metric(900, "tokens", "ESTIMATED"), evidence_call_ids: [1, 2], proposal_id: null };
    const out = html(h(advisor.FindingsList, { findings: [f] }));
    expect(out).toContain("R1");
    expect(out).toContain("근거 호출 2 건");
  });
});

describe("profile", () => {
  it("renders stats, recommendations and the form with integer fields", () => {
    const out = html(h(profile.ProfileView, {
      profile: { monthly_budget_microusd: 5_000_000, store_bodies: false },
      stats: [{ task_kind: "bug", model_id: "m1", structure: "A", context_mode: "fresh", tasks: 4, correct: 3, tokens_per_correct: metric(1234, "tokens", "CALCULATED") }],
      recommendations: [{ id: "r", headline: "구조 B 추천", current_config: {}, recommended_config: {}, saving: metric(10, "microusd", "ESTIMATED"), evidence_n: 3 }],
      onSave() {},
    }));
    expect(out).toContain("1,234");
    expect(out).toContain("구조 B 추천");
    expect(out).toContain('value="5000000"');
    expect(out).toContain('step="1"');
  });
});

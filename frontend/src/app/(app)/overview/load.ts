import type { ApiClient, Schemas } from "../../../lib/api";

export type OverviewData = { summary: Schemas["UsageSummary"]; budgets: Schemas["Budget"][] };

/** overview reads only /usage/summary and /budgets. */
export async function loadOverview(client: ApiClient, ws: string): Promise<OverviewData> {
  const [summary, budgets] = await Promise.all([
    client.get("/v1/workspaces/{ws}/usage/summary", { params: { ws } }),
    client.get("/v1/workspaces/{ws}/budgets", { params: { ws } }),
  ]);
  return { summary, budgets };
}

/** Budget use in permille: the workspace/month budget's list use over its limit, else the summary tile. */
export function budgetUsePermille(d: OverviewData): { value: number | null; provenance: Schemas["Provenance"] } {
  const b = d.budgets.find((x) => x.scope === "workspace" && x.period === "month" && x.limit_microusd > 0);
  const used = b ? (b.measure === "cli" ? b.used.cli.value : b.used.list.value) : null;
  if (b && used !== null) return { value: Math.round((used * 1000) / b.limit_microusd), provenance: "CALCULATED" };
  return { value: d.summary.tiles.budget_use.value, provenance: d.summary.tiles.budget_use.provenance };
}

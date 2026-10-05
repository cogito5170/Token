import type { Schemas } from "../../../lib/api";
import { provenanceLine } from "../../../lib/charts/theme";
import { formatMicroUsd, formatTokensCompact } from "../../../lib/format";

export const TREND_SERIES = ["total_tokens", "cost_list", "cost_cli"] as const;
const LABEL: Record<string, string> = { total_tokens: "토큰", cost_list: "비용(정가)", cost_cli: "비용(CLI)" };

/** ECharts option: tokens on the left axis, both cost measures on the right; line style follows provenance. */
export function trendOption(series: Schemas["Series"][]) {
  const picked = TREND_SERIES.map((n) => series.find((s) => s.name === n)).filter((s): s is Schemas["Series"] => !!s);
  return {
    tooltip: { trigger: "axis" },
    legend: { data: picked.map((s) => LABEL[s.name]) },
    xAxis: { type: "category", data: picked[0]?.points.map((p) => p[0]) ?? [] },
    yAxis: [
      { type: "value", axisLabel: { formatter: (v: number) => formatTokensCompact(v) } },
      { type: "value", axisLabel: { formatter: (v: number) => formatMicroUsd(v) }, splitLine: { show: false } },
    ],
    series: picked.map((s) => ({
      name: LABEL[s.name], type: "line", yAxisIndex: s.unit === "tokens" ? 0 : 1, showSymbol: false, connectNulls: false,
      lineStyle: { type: provenanceLine(s.provenance) },
      data: s.points.map((p) => p[1]),
    })),
  };
}

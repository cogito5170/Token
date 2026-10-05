import type { Schemas } from "../../../lib/api";
import { provenanceLine } from "../../../lib/charts/theme";
import { formatTokensCompact } from "../../../lib/format";
import { MIX, MIX_LABEL, type MixName } from "./load";

/** Stacked area, one layer per token kind; MEASURED -> solid line, full fill. */
export function mixOption(series: Schemas["Series"][], title?: string) {
  const kinds = MIX.map((k) => ({ k, s: series.find((s) => s.name === k || s.name.endsWith(`:${k}`)) }))
    .filter((x): x is { k: MixName; s: Schemas["Series"] } => !!x.s);
  return {
    title: title ? { text: title, textStyle: { fontSize: 13 } } : undefined,
    tooltip: { trigger: "axis" },
    legend: { data: kinds.map((x) => MIX_LABEL[x.k]) },
    xAxis: { type: "category", boundaryGap: false, data: kinds[0]?.s.points.map((p) => p[0]) ?? [] },
    yAxis: { type: "value", axisLabel: { formatter: (v: number) => formatTokensCompact(v) } },
    series: kinds.map(({ k, s }) => ({
      name: MIX_LABEL[k], type: "line", stack: "tokens", showSymbol: false,
      lineStyle: { type: provenanceLine(s.provenance) },
      areaStyle: { opacity: s.provenance === "MEASURED" ? 1 : 0.7 },
      data: s.points.map((p) => p[1]),
    })),
  };
}

import type { Schemas } from "../../../lib/api";
import { formatTokensCompact } from "../../../lib/format";

/** Histogram bars over log2 bins, a vertical threshold line and clickable outlier dots (x = category of the bin). */
export function histOption(h: Schemas["Histogram"]) {
  const cats = h.bins.map((b) => `${formatTokensCompact(b.lo)}–${formatTokensCompact(b.hi)}`);
  const binOf = (v: number) => Math.max(0, h.bins.findIndex((b) => v >= b.lo && v < b.hi));
  const thrBin = h.bins.findIndex((b) => h.threshold >= b.lo && h.threshold < b.hi);
  return {
    tooltip: { trigger: "item" },
    xAxis: { type: "category", data: cats, name: "문맥 토큰" },
    yAxis: { type: "value", name: "호출" },
    series: [
      {
        name: "호출 수", type: "bar", data: h.bins.map((b) => b.count),
        markLine: thrBin >= 0 ? { symbol: "none", data: [{ xAxis: thrBin, label: { formatter: formatTokensCompact(h.threshold) } }] } : undefined,
      },
      {
        name: "이상치", type: "scatter",
        data: h.outliers.map((o) => ({ value: [binOf(o.context_tokens), 0], call_id: o.call_id, context_tokens: o.context_tokens })),
      },
    ],
  };
}

import type { components } from "../api/schema";
import { EM_DASH, formatCount, formatMicroUsd, formatPermille, formatTokens } from "./money";

type Metric = components["schemas"]["Metric"];

/** Render a Metric by its unit. value null -> "—". */
export function formatMetric(m: Pick<Metric, "value" | "unit">): string {
  switch (m.unit) {
    case "microusd": return formatMicroUsd(m.value);
    case "tokens": return formatTokens(m.value);
    case "permille": return formatPermille(m.value);
    case "ms": return m.value === null ? EM_DASH : `${formatTokens(m.value)} ms`;
    default: return formatCount(m.value);
  }
}

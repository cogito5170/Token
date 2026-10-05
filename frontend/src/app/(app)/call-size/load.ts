import type { ApiClient, Schemas } from "../../../lib/api";

/** call_size reads /usage/series/call-size; the call list only when an outlier is opened. */
export function loadCallSize(client: ApiClient, ws: string): Promise<Schemas["Histogram"]> {
  return client.get("/v1/workspaces/{ws}/usage/series/call-size", { params: { ws } });
}
export function loadOutlierCalls(client: ApiClient, ws: string, threshold: number): Promise<Schemas["CallPage"]> {
  return client.get("/v1/workspaces/{ws}/usage/calls", { params: { ws }, query: { min_input: threshold } });
}

/** Percentile (permille, e.g. 500 = median) from log bins, linear inside the bin; null when empty. */
export function binPercentile(bins: Schemas["Histogram"]["bins"], permille: number): number | null {
  const total = bins.reduce((a, b) => a + b.count, 0);
  if (total === 0) return null;
  const target = (total * permille) / 1000;
  let acc = 0;
  for (const b of bins) {
    if (acc + b.count >= target && b.count > 0) return Math.round(b.lo + ((b.hi - b.lo) * (target - acc)) / b.count);
    acc += b.count;
  }
  return bins[bins.length - 1].hi;
}

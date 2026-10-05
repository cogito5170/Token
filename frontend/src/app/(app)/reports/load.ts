import type { ApiClient, FetchLike, Schemas } from "../../../lib/api/client";

export function listReports(client: ApiClient, ws: string) {
  return client.get("/v1/workspaces/{ws}/reports", {
    params: { ws },
  });
}

export function generateReport(
  client: ApiClient,
  ws: string,
  period: { from: string; to: string }
) {
  return client.post("/v1/workspaces/{ws}/reports", {
    params: { ws },
    body: period,
  });
}

export function exportReport(client: ApiClient, ws: string, id: string) {
  return client.get("/v1/workspaces/{ws}/reports/{report}/export", {
    params: { ws, report: id },
    query: { format: "json" },
  });
}

export async function exportCsv(
  f: FetchLike,
  base: string,
  token: string | null,
  ws: string,
  id: string
): Promise<string> {
  const url = `${base}/v1/workspaces/${encodeURIComponent(
    ws
  )}/reports/${encodeURIComponent(id)}/export?format=csv`;
  const res = await f(url, {
    headers: token ? { authorization: `Bearer ${token}` } : {},
    credentials: "include",
  });
  if (!res.ok) {
    throw new Error(`Failed to export CSV: ${res.status} ${res.statusText}`);
  }
  return await res.text();
}

export function reportFileName(
  r: Schemas["Report"],
  format: "csv" | "json"
): string {
  return `report-${r.period.from}_${r.period.to}.${format}`;
}

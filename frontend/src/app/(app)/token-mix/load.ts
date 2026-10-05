import type { ApiClient, Schemas } from "../../../lib/api";

export const MIX = ["input", "cache_read", "cache_write", "output"] as const;
export type MixName = (typeof MIX)[number];
export const MIX_LABEL: Record<MixName, string> = { input: "입력", cache_read: "캐시 읽기", cache_write: "캐시 쓰기", output: "출력" };

/** token_mix reads only /usage/series/tokens. */
export function loadTokenMix(client: ApiClient, ws: string, groupBy: "none" | "model"): Promise<Schemas["SeriesSet"]> {
  return client.get("/v1/workspaces/{ws}/usage/series/tokens", { params: { ws }, query: { group_by: groupBy } });
}

const sum = (s?: Schemas["Series"]) => (s?.points ?? []).reduce((a, p) => a + (p[1] ?? 0), 0);

/** Share of each kind in permille over all series (integer, rounded half-up). */
export function mixShares(set: Schemas["SeriesSet"]): Record<MixName, number | null> {
  const tot: Record<MixName, number> = { input: 0, cache_read: 0, cache_write: 0, output: 0 };
  for (const s of set.series) {
    const kind = MIX.find((k) => s.name === k || s.name.endsWith(`:${k}`));
    if (kind) tot[kind] += sum(s);
  }
  const all = MIX.reduce((a, k) => a + tot[k], 0);
  const out = {} as Record<MixName, number | null>;
  for (const k of MIX) out[k] = all === 0 ? null : Math.floor((tot[k] * 1000 * 2 + all) / (all * 2));
  return out;
}

/** Group series by model prefix ("<model>:<kind>"); ungrouped series land under "". */
export function byModel(set: Schemas["SeriesSet"]): Map<string, Schemas["Series"][]> {
  const m = new Map<string, Schemas["Series"][]>();
  for (const s of set.series) {
    const i = s.name.lastIndexOf(":");
    const model = i < 0 ? "" : s.name.slice(0, i);
    (m.get(model) ?? m.set(model, []).get(model)!).push(s);
  }
  return m;
}

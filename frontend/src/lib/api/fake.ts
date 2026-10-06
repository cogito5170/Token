import type { FetchLike, Schemas } from "./client";

export interface FakeCall { method: string; path: string; query: Record<string, string>; body: unknown }
export type FakeHandler = (call: FakeCall, params: Record<string, string>) => { status?: number; body?: unknown } | unknown;

const WS = "00000000-0000-4000-8000-000000000001";
const USER = "00000000-0000-4000-8000-0000000000a1";

const metric = (value: number | null, unit: Schemas["Unit"], provenance: Schemas["Provenance"], extra: object = {}) => ({
  value, unit, provenance, ...extra,
});

export const fixtures = {
  workspace: { id: WS, name: "데모 워크스페이스", slug: "demo", role: "admin" } satisfies Schemas["Workspace"],
  user: { id: USER, email: "demo@example.com", display_name: "Demo" } satisfies Schemas["User"],
  usageSummary: {
    period: { from: "2026-09-01", to: "2026-09-30" },
    tiles: {
      total_tokens: metric(12_345_678, "tokens", "MEASURED"),
      cost_list: metric(1234, "microusd", "CALCULATED"),
      cost_cli: metric(null, "microusd", "MEASURED", { coverage_permille: 0 }),
      correct_tasks: metric(42, "tasks", "MEASURED"),
      cost_list_per_correct: metric(29, "microusd", "CALCULATED"),
      cost_cli_per_correct: metric(null, "microusd", "CALCULATED"),
      budget_use: metric(412, "permille", "CALCULATED"),
    },
    trend: { bucket: "day", series: [] },
  } satisfies Schemas["UsageSummary"],
};

/** Route table keyed "METHOD /v1/path/{param}". Screens may extend it per test. */
export function defaultHandlers(): Record<string, FakeHandler> {
  return {
    "POST /v1/auth/login": () => ({ access_token: "fake-access-token", expires_in: 900 }),
    "POST /v1/auth/signup": () => ({ status: 201, body: { access_token: "fake-access-token", expires_in: 900 } }),
    "POST /v1/auth/refresh": () => ({ access_token: "fake-access-token", expires_in: 900 }),
    "POST /v1/auth/logout": () => ({ status: 204 }),
    "GET /v1/me": () => fixtures.user,
    "GET /v1/workspaces": () => [fixtures.workspace],
    "GET /v1/workspaces/{ws}": () => fixtures.workspace,
    "GET /v1/workspaces/{ws}/usage/summary": () => fixtures.usageSummary,
  };
}

function match(pattern: string, path: string): Record<string, string> | null {
  const a = pattern.split("/"), b = path.split("/");
  if (a.length !== b.length) return null;
  const params: Record<string, string> = {};
  for (let i = 0; i < a.length; i++) {
    const m = /^\{(\w+)\}$/.exec(a[i]);
    if (m) params[m[1]] = decodeURIComponent(b[i]);
    else if (a[i] !== b[i]) return null;
  }
  return params;
}

/** A fetch implementation backed by handlers. `calls` is the spy list (screens assert on listed paths). */
export function createFakeFetch(extra: Record<string, FakeHandler> = {}) {
  const handlers = { ...defaultHandlers(), ...extra };
  const calls: FakeCall[] = [];
  const fetchLike: FetchLike = async (input, init) => {
    const u = new URL(input, "http://fake.local");
    const method = (init?.method ?? "GET").toUpperCase();
    const call: FakeCall = {
      method, path: u.pathname,
      query: Object.fromEntries(u.searchParams),
      body: init?.body ? JSON.parse(String(init.body)) : undefined,
    };
    calls.push(call);
    for (const [key, h] of Object.entries(handlers)) {
      const [m, p] = key.split(" ");
      if (m !== method) continue;
      const params = match(p, u.pathname);
      if (!params) continue;
      const r = h(call, params) as { status?: number; body?: unknown } | undefined;
      const keys = r && typeof r === "object" ? Object.keys(r) : [];
      const wrapped = keys.length > 0 && keys.every(k => k === "status" || k === "body");
      const status = wrapped ? (r.status ?? 200) : 200;
      const body = wrapped ? r.body : r;
      return new Response(status === 204 ? null : JSON.stringify(body ?? null), {
        status, headers: { "content-type": "application/json" },
      });
    }
    return new Response(JSON.stringify({ code: "not_found", message: `fake: no handler for ${method} ${u.pathname}` }), { status: 404 });
  };
  return { fetch: fetchLike, calls };
}

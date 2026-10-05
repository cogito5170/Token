import type { paths, components } from "./schema";

export type Schemas = components["schemas"];
export type ApiPaths = paths;
export type FetchLike = (input: string, init?: RequestInit) => Promise<Response>;

export class ApiError extends Error {
  constructor(public status: number, public body: Schemas["Error"] | null) {
    super(body?.message ?? `HTTP ${status}`);
  }
}

type Method = "get" | "post" | "put" | "patch" | "delete";
type JsonOf<T> = T extends { content: { "application/json": infer B } } ? B : never;
type OkBody<Op> = Op extends { responses: infer R }
  ? JsonOf<R[Extract<keyof R, 200 | 201>]>
  : never;
type ReqBody<Op> = Op extends { requestBody?: infer B } ? JsonOf<NonNullable<B>> : never;
type Query<Op> = Op extends { parameters: { query?: infer Q } } ? NonNullable<Q> : never;

export interface Options<Op> {
  params?: Record<string, string>;
  query?: Query<Op> | Record<string, string | number | undefined>;
  body?: ReqBody<Op>;
}

export interface ClientConfig {
  baseUrl?: string;
  fetch?: FetchLike;
  getToken?: () => string | null;
}

export function createClient(cfg: ClientConfig = {}) {
  const base = cfg.baseUrl ?? process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
  const f: FetchLike = cfg.fetch ?? ((i, init) => fetch(i, init));

  async function request<P extends keyof paths, M extends Method & keyof paths[P]>(
    method: M,
    path: P,
    opts: Options<paths[P][M]> = {},
  ): Promise<OkBody<paths[P][M]>> {
    let url = String(path).replace(/\{(\w+)\}/g, (_, k) => {
      const v = opts.params?.[k];
      if (v === undefined) throw new Error(`missing path param ${k} for ${String(path)}`);
      return encodeURIComponent(v);
    });
    const q = Object.entries((opts.query ?? {}) as Record<string, unknown>)
      .filter(([, v]) => v !== undefined)
      .map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(String(v))}`);
    if (q.length) url += `?${q.join("&")}`;
    const headers: Record<string, string> = {};
    const token = cfg.getToken?.();
    if (token) headers.authorization = `Bearer ${token}`;
    if (opts.body !== undefined) headers["content-type"] = "application/json";
    const res = await f(base + url, {
      method: String(method).toUpperCase(),
      headers,
      credentials: "include",
      body: opts.body === undefined ? undefined : JSON.stringify(opts.body),
    });
    if (!res.ok) {
      let body: Schemas["Error"] | null = null;
      try { body = await res.json(); } catch { /* not json */ }
      throw new ApiError(res.status, body);
    }
    if (res.status === 204) return undefined as OkBody<paths[P][M]>;
    return (await res.json()) as OkBody<paths[P][M]>;
  }

  return {
    request,
    get: <P extends keyof paths>(path: P, opts?: Options<paths[P] extends { get: infer G } ? G : never>) =>
      request("get" as never, path as never, opts as never) as Promise<OkBody<paths[P] extends { get: infer G } ? G : never>>,
    post: <P extends keyof paths>(path: P, opts?: Options<paths[P] extends { post: infer G } ? G : never>) =>
      request("post" as never, path as never, opts as never) as Promise<OkBody<paths[P] extends { post: infer G } ? G : never>>,
  };
}

export type ApiClient = ReturnType<typeof createClient>;

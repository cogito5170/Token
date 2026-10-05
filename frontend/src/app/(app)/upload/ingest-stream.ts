import type { Schemas } from "../../../lib/api";

export type IngestEvent = Schemas["IngestJobEvent"];
export type IngestStreamEvent = { id: string | null; event: string; data: IngestEvent };
export interface SseFrame { id: string | null; event: string; data: string }

/** Incremental SSE parser: feed text chunks, get complete frames. Comment lines (heartbeats) are skipped. */
export function createSseParser() {
  let buf = "";
  return (chunk: string): SseFrame[] => {
    buf += chunk.replace(/\r\n/g, "\n");
    const out: SseFrame[] = [];
    let i: number;
    while ((i = buf.indexOf("\n\n")) >= 0) {
      const block = buf.slice(0, i);
      buf = buf.slice(i + 2);
      let id: string | null = null, event = "message";
      const data: string[] = [];
      for (const line of block.split("\n")) {
        if (line.startsWith(":") || line === "") continue;
        const c = line.indexOf(":");
        const k = c < 0 ? line : line.slice(0, c);
        const v = c < 0 ? "" : line.slice(c + 1).replace(/^ /, "");
        if (k === "id") id = v; else if (k === "event") event = v; else if (k === "data") data.push(v);
      }
      if (data.length) out.push({ id, event, data: data.join("\n") });
    }
    return out;
  };
}

export interface FollowOptions {
  url: string;
  fetch?: (input: string, init?: RequestInit) => Promise<Response>;
  headers?: Record<string, string>;
  onEvent: (e: IngestStreamEvent) => void;
  signal?: AbortSignal;
  /** Delay before a reconnect; tests pass 0. */
  retryMs?: number;
  maxRetries?: number;
}

/**
 * Follow an ingest job's SSE stream until `done` or `failed`. When the connection drops, reconnect
 * with the `Last-Event-ID` of the last event seen so the server resumes after it.
 * Resolves with the terminal event name; rejects after maxRetries consecutive failed connects.
 */
export async function followIngestJob(o: FollowOptions): Promise<"done" | "failed" | "aborted"> {
  const f = o.fetch ?? ((i, init) => fetch(i, init));
  let lastId: string | null = null;
  let failures = 0;
  while (!o.signal?.aborted) {
    try {
      const headers: Record<string, string> = { accept: "text/event-stream", ...o.headers };
      if (lastId !== null) headers["last-event-id"] = lastId;
      const res = await f(o.url, { headers, signal: o.signal, credentials: "include" });
      if (!res.ok || !res.body) throw new Error(`HTTP ${res.status}`);
      failures = 0;
      const parse = createSseParser();
      const reader = res.body.getReader();
      const dec = new TextDecoder();
      for (;;) {
        const { done, value } = await reader.read();
        if (done) break;
        for (const fr of parse(dec.decode(value, { stream: true }))) {
          if (fr.id !== null) lastId = fr.id;
          const ev = { id: fr.id, event: fr.event, data: JSON.parse(fr.data) as IngestEvent };
          o.onEvent(ev);
          if (fr.event === "done" || fr.event === "failed") return fr.event;
        }
      }
    } catch (err) {
      if (o.signal?.aborted) break;
      if (++failures > (o.maxRetries ?? 5)) throw err;
    }
    await new Promise((r) => setTimeout(r, o.retryMs ?? 1000));
  }
  return "aborted";
}

export const STAGE_LABEL: Record<Schemas["IngestState"], string> = {
  queued: "대기 중", parsing: "파싱", normalizing: "정규화", loading: "적재", analyzing: "분석", done: "완료", failed: "실패",
};

/** Progress percentage clamped to 0..100 (integer). */
export const clampPct = (pct: number) => Math.max(0, Math.min(100, Math.round(pct)));

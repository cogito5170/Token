// CMD-FE2: where events come from. Live: SSE of MonitorEvent (openapi /monitor/sources/{source}/events,
// `id: <seq>`, `event: <kind>`, `data: <MonitorEvent JSON>`, resume with Last-Event-ID). Replay: the recorded
// JSONL (/monitor/sources/{source}/recordings/{recording}). Read-only: nothing here writes anywhere.
import type { MonitorEvent } from "./types";

export function parseRecording(text: string): MonitorEvent[] {
  return text.split("\n").filter((l) => l.trim()).map((l) => JSON.parse(l) as MonitorEvent);
}

/** Adds events by seq, dropping repeats (a resumed stream can resend the last one). */
export function merge(into: readonly MonitorEvent[], add: readonly MonitorEvent[]): MonitorEvent[] {
  const seen = new Set(into.map((e) => e.seq));
  const out = [...into];
  for (const e of add) if (!seen.has(e.seq)) { seen.add(e.seq); out.push(e); }
  return out.sort((a, b) => a.seq - b.seq);
}

/** Parses SSE frames out of a growing buffer; returns the events and the unconsumed rest. */
export function parseSse(buf: string): { events: MonitorEvent[]; rest: string } {
  const events: MonitorEvent[] = [];
  const blocks = buf.split(/\r?\n\r?\n/);
  const rest = blocks.pop() ?? "";
  for (const b of blocks) {
    const data = b.split(/\r?\n/).filter((l) => l.startsWith("data:")).map((l) => l.slice(5).replace(/^ /, "")).join("\n");
    if (data) events.push(JSON.parse(data) as MonitorEvent);
  }
  return { events, rest };
}

export interface Endpoint {
  base: string; // e.g. http://127.0.0.1:8765
  ws: string;
  source: string;
  token?: string | null;
}

const path = (ep: Endpoint, tail: string) =>
  `${ep.base}/v1/workspaces/${encodeURIComponent(ep.ws)}/monitor/sources/${encodeURIComponent(ep.source)}${tail}`;
const auth = (ep: Endpoint): Record<string, string> => (ep.token ? { authorization: `Bearer ${ep.token}` } : {});

export async function fetchRecording(ep: Endpoint, recording: string, f: typeof fetch = fetch): Promise<MonitorEvent[]> {
  const res = await f(path(ep, `/recordings/${encodeURIComponent(recording)}`), { headers: auth(ep), credentials: "include" });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return parseRecording(await res.text());
}

/** Follows the live stream until aborted, reconnecting with Last-Event-ID. */
export async function follow(ep: Endpoint, onEvents: (evs: MonitorEvent[]) => void, signal: AbortSignal, f: typeof fetch = fetch) {
  let last: number | null = null;
  while (!signal.aborted) {
    try {
      const headers: Record<string, string> = { ...auth(ep), accept: "text/event-stream" };
      if (last !== null) headers["Last-Event-ID"] = String(last);
      const res = await f(path(ep, "/events"), { headers, credentials: "include", signal });
      if (!res.ok || !res.body) throw new Error(`HTTP ${res.status}`);
      const reader = res.body.getReader();
      const dec = new TextDecoder();
      let buf = "";
      for (;;) {
        const { value, done } = await reader.read();
        if (done) break;
        const out = parseSse((buf += dec.decode(value, { stream: true })));
        buf = out.rest;
        if (out.events.length) {
          last = out.events[out.events.length - 1].seq;
          onEvents(out.events);
        }
      }
    } catch {
      if (signal.aborted) return;
    }
    await new Promise((r) => setTimeout(r, 1000));
  }
}

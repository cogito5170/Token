import { describe, expect, it } from "vitest";
import { readFileSync, existsSync } from "node:fs";
import { resolve } from "node:path";
import { followIngestJob, createSseParser, clampPct, type IngestStreamEvent } from "../../src/app/(app)/upload/ingest-stream";
import { canViewAudit } from "../../src/app/(app)/audit/access";
import { buildNav } from "../../src/lib/nav/registry";
import { scanRoutes } from "../../src/lib/nav/scan";

const enc = new TextEncoder();
const frame = (seq: number, event: string, pct: number, stage = "parsing") =>
  `id: ${seq}\nevent: ${event}\ndata: ${JSON.stringify({ seq, stage, pct, counts: { inserted: seq } })}\n\n`;

/** A response whose body yields the chunks, then closes (or errors when `drop` is set). */
const stream = (chunks: string[]) =>
  new Response(new ReadableStream({
    start(c) { for (const x of chunks) c.enqueue(enc.encode(x)); c.close(); },
  }), { status: 200 });

describe("SSE parser", () => {
  it("skips heartbeats and reassembles frames split across chunks", () => {
    const p = createSseParser();
    const f = frame(1, "progress", 10);
    expect(p(": hb\n\n" + f.slice(0, 15))).toEqual([]);
    const out = p(f.slice(15));
    expect(out).toHaveLength(1);
    expect(out[0].id).toBe("1");
    expect(out[0].event).toBe("progress");
  });
});

describe("ingest progress", () => {
  it("follows a scripted stream to done", async () => {
    const seen: IngestStreamEvent[] = [];
    const res = await followIngestJob({
      url: "http://x/events", retryMs: 0,
      fetch: async () => stream([frame(1, "progress", 20), frame(2, "progress", 60, "loading"), frame(3, "done", 100, "done")]),
      onEvent: (e) => seen.push(e),
    });
    expect(res).toBe("done");
    expect(seen.map((e) => e.data.pct)).toEqual([20, 60, 100]);
  });

  it("resumes with Last-Event-ID after the connection drops", async () => {
    const sent: (string | undefined)[] = [];
    const seen: number[] = [];
    let n = 0;
    const res = await followIngestJob({
      url: "http://x/events", retryMs: 0,
      fetch: async (_u, init) => {
        sent.push((init?.headers as Record<string, string>)["last-event-id"]);
        n++;
        if (n === 1) return stream([frame(1, "progress", 10), frame(2, "progress", 40)]); // drops mid-job
        return stream([frame(3, "progress", 80), frame(4, "done", 100, "done")]);
      },
      onEvent: (e) => seen.push(e.data.seq),
    });
    expect(res).toBe("done");
    expect(sent).toEqual([undefined, "2"]);
    expect(seen).toEqual([1, 2, 3, 4]);
  });

  it("retries after a failed connect and stops on failed", async () => {
    let n = 0;
    const res = await followIngestJob({
      url: "http://x/events", retryMs: 0,
      fetch: async () => (++n === 1 ? new Response("", { status: 503 }) : stream([frame(1, "failed", 30, "failed")])),
      onEvent: () => {},
    });
    expect(res).toBe("failed");
    expect(n).toBe(2);
  });

  it("clamps progress to 0..100", () => {
    expect([clampPct(-5), clampPct(42.4), clampPct(130)]).toEqual([0, 42, 100]);
  });
});

describe("audit access", () => {
  it("is visible only to admins", () => {
    expect(canViewAudit("admin")).toBe(true);
    for (const r of ["developer", "viewer", null, undefined] as const) expect(canViewAudit(r as never)).toBe(false);
  });

  it("nav hides the audit page for non-admin", () => {
    const entries = scanRoutes(resolve(__dirname, "../../src/app"));
    const hrefs = (isAdmin: boolean) => buildNav(entries, { isAdmin }).flatMap((g) => g.items.map((i) => i.href));
    expect(hrefs(false)).not.toContain("/audit");
    expect(hrefs(true)).toContain("/audit");
    expect(hrefs(false)).toEqual(expect.arrayContaining(["/upload", "/notifications"]));
  });

  it("audit page renders nothing and requests nothing without the admin check", () => {
    const src = readFileSync(resolve(__dirname, "../../src/app/(app)/audit/page.tsx"), "utf8");
    expect(src).toContain("canViewAudit(role)");
    expect(existsSync(resolve(__dirname, "../../src/app/(app)/audit/access.ts"))).toBe(true);
  });
});

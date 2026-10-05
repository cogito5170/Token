"use client";
import { useRef, useState, type FormEvent } from "react";
import { api, ApiError } from "../../../lib/api";
import { getAccessToken, getWorkspaceId } from "../../../lib/auth/session";
import { followIngestJob, clampPct, STAGE_LABEL, type IngestEvent } from "./ingest-stream";

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export default function Page() {
  const [event, setEvent] = useState<IngestEvent | null>(null);
  const [outcome, setOutcome] = useState<"done" | "failed" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const abort = useRef<AbortController | null>(null);

  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null); setOutcome(null); setEvent(null);
    const ws = getWorkspaceId();
    if (!ws) { setError("워크스페이스를 먼저 선택하세요."); return; }
    const form = new FormData(e.currentTarget);
    try {
      const token = getAccessToken();
      const res = await fetch(`${BASE}/v1/workspaces/${ws}/uploads`, {
        method: "POST", body: form, credentials: "include",
        headers: token ? { authorization: `Bearer ${token}` } : undefined,
      });
      if (!res.ok) throw new ApiError(res.status, await res.json().catch(() => null));
      const upload = (await res.json()) as { job_id: string };
      abort.current?.abort();
      abort.current = new AbortController();
      const result = await followIngestJob({
        url: `${BASE}/v1/workspaces/${ws}/ingest-jobs/${upload.job_id}/events`,
        headers: token ? { authorization: `Bearer ${token}` } : undefined,
        signal: abort.current.signal,
        onEvent: (ev) => setEvent(ev.data),
      });
      if (result !== "aborted") setOutcome(result);
    } catch (err) {
      setError(err instanceof ApiError ? (err.status === 413 ? "파일이 너무 큽니다." : err.message) : "업로드에 실패했습니다.");
    }
  }

  const pct = event ? clampPct(event.pct) : 0;
  return (
    <section>
      <h1>업로드</h1>
      <form onSubmit={submit}>
        <label>소스 ID<input name="source_id" required /></label>
        <label>파일<input name="file" type="file" required /></label>
        <button type="submit">업로드</button>
      </form>
      {error && <p className="gc-error" role="alert">{error}</p>}
      {event && (
        <div>
          <progress value={pct} max={100} aria-label="수집 진행률" />
          <p>{STAGE_LABEL[event.stage]} · {pct}%</p>
          <p>적재 {event.counts.inserted ?? 0} · 중복 {event.counts.duplicates ?? 0} · 거부 {event.counts.rejected ?? 0}</p>
        </div>
      )}
      {outcome === "done" && <p role="status">수집이 완료되었습니다.</p>}
      {outcome === "failed" && <p className="gc-error" role="alert">수집에 실패했습니다.</p>}
    </section>
  );
}

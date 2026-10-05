"""Ingestion use cases: job state machine, pipeline, retries, progress events. Store, upload opener, loader and
publisher are injected so the pipeline runs without a database.

States: queued -> parsing -> normalizing -> loading -> analyzing -> done | failed. A failed attempt goes back to
queued until MAX_ATTEMPTS, then failed. Errors are recorded as a code only (never a message, line or content).
"""
from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, Protocol

from . import registry

MAX_ATTEMPTS = 3
MAX_REJECT_ROWS = 10000
STAGES = {"parsing": 10, "normalizing": 40, "loading": 70, "analyzing": 90, "done": 100}
TERMINAL = ("done", "failed")


class IngestError(Exception):
    """Pipeline failure carrying only a short code (also used for HTTP 404 with code not_found)."""

    def __init__(self, code: str, status: int = 422):
        super().__init__(code)
        self.code, self.status = code, status


@dataclass
class JobRow:
    id: str
    workspace_id: str
    upload_id: str
    state: str = "queued"
    source_kind: str | None = None
    parser: str | None = None
    attempts: int = 0
    inserted: int = 0
    duplicates: int = 0
    rejected: int = 0
    last_error_code: str | None = None
    created_at: datetime | None = None
    finished_at: datetime | None = None


@dataclass
class Claimed:
    job: JobRow
    source_id: str
    declared_format: str | None = None


@dataclass
class EventRow:
    seq: int
    stage: str
    pct: int
    counts: dict = field(default_factory=dict)


class Store(Protocol):
    def enqueue(self, upload_id: str) -> str: ...
    def claim(self, worker: str) -> Claimed | None: ...
    def advance(self, job_id: str, state: str, pct: int, counts: dict | None = None) -> int: ...
    def set_format(self, job_id: str, kind: str, parser: str) -> None: ...
    def add_rejects(self, job_id: str, rejects: list[tuple[int, str]]) -> None: ...
    def finish(self, job_id: str, counts: dict, lines_total: int) -> int: ...
    def fail_attempt(self, job_id: str, code: str, max_attempts: int) -> tuple[str, int]: ...
    def job(self, ws: str, job_id: str) -> JobRow | None: ...
    def jobs(self, ws: str) -> list[JobRow]: ...
    def events_after(self, job_id: str, seq: int) -> list[EventRow]: ...
    def wait(self, job_id: str, seq: int, timeout: float) -> None: ...


class MemoryStore:
    """Thread-safe in-memory store (tests). `uploads` maps upload_id -> (workspace_id, source_id, declared_format)."""

    def __init__(self) -> None:
        self.lock = threading.Condition()
        self.uploads: dict[str, tuple[str, str, str | None]] = {}
        self.src: dict[str, tuple[str, str | None]] = {}
        self.rows: dict[str, JobRow] = {}
        self.ev: dict[str, list[EventRow]] = {}
        self.rej: dict[str, list[tuple[int, str]]] = {}
        self.lines: dict[str, int] = {}

    def register_upload(self, upload_id: str, ws: str, source_id: str, declared: str | None = None) -> None:
        self.uploads[upload_id] = (ws, source_id, declared)

    def _event(self, j: JobRow, stage: str, pct: int, counts: dict | None) -> int:
        evs = self.ev.setdefault(j.id, [])
        evs.append(EventRow(len(evs) + 1, stage, pct, dict(counts or {})))
        self.lock.notify_all()
        return len(evs)

    def enqueue(self, upload_id):
        with self.lock:
            if upload_id not in self.uploads:
                raise IngestError("not_found", 404)
            for j in self.rows.values():
                if j.upload_id == upload_id and j.state not in TERMINAL:
                    return j.id
            ws = self.uploads[upload_id][0]
            j = JobRow(str(uuid.uuid4()), ws, upload_id, created_at=datetime.now(timezone.utc))
            self.rows[j.id] = j
            self._event(j, "queued", 0, None)
            return j.id

    def claim(self, worker):
        with self.lock:
            for j in sorted(self.rows.values(), key=lambda r: r.created_at):
                if j.state == "queued":
                    j.state, j.attempts = "parsing", j.attempts + 1
                    self._event(j, "parsing", STAGES["parsing"], None)
                    ws, src, fmt = self.uploads[j.upload_id]
                    return Claimed(JobRow(**j.__dict__), src, fmt)
        return None

    def advance(self, job_id, state, pct, counts=None):
        with self.lock:
            j = self.rows[job_id]
            j.state = state
            return self._event(j, state, pct, counts)

    def set_format(self, job_id, kind, parser):
        with self.lock:
            self.rows[job_id].source_kind, self.rows[job_id].parser = kind, parser

    def add_rejects(self, job_id, rejects):
        with self.lock:
            self.rej.setdefault(job_id, []).extend(rejects[:MAX_REJECT_ROWS])

    def finish(self, job_id, counts, lines_total):
        with self.lock:
            j = self.rows[job_id]
            j.inserted, j.duplicates, j.rejected = counts["inserted"], counts["duplicates"], counts["rejected"]
            j.finished_at = datetime.now(timezone.utc)
            self.lines[job_id] = lines_total
            j.state = "done"
            return self._event(j, "done", 100, counts)

    def fail_attempt(self, job_id, code, max_attempts):
        with self.lock:
            j = self.rows[job_id]
            j.last_error_code = code
            if j.attempts < max_attempts:
                j.state = "queued"
                return "queued", self._event(j, "queued", 0, None)
            j.state, j.finished_at = "failed", datetime.now(timezone.utc)
            return "failed", self._event(j, "failed", 0, None)

    def job(self, ws, job_id):
        j = self.rows.get(job_id)
        return JobRow(**j.__dict__) if j and j.workspace_id == ws else None

    def jobs(self, ws):
        return [JobRow(**j.__dict__) for j in sorted(self.rows.values(), key=lambda r: r.created_at, reverse=True)
                if j.workspace_id == ws]

    def events_after(self, job_id, seq):
        with self.lock:
            return [EventRow(e.seq, e.stage, e.pct, dict(e.counts)) for e in self.ev.get(job_id, []) if e.seq > seq]

    def wait(self, job_id, seq, timeout):
        with self.lock:
            if len(self.ev.get(job_id, [])) <= seq:
                self.lock.wait(timeout)


class IngestService:
    def __init__(self, store: Store, open_upload: Callable, load_calls: Callable, get_source: Callable,
                 publish: Callable[[str, dict], object] | None = None, max_attempts: int = MAX_ATTEMPTS) -> None:
        self.store, self.open_upload, self.load_calls, self.get_source = store, open_upload, load_calls, get_source
        self.publish = publish or (lambda n, p: 0)
        self.max_attempts = max_attempts

    # ---- enqueue (hook for source: Upload.job_id) ----
    def enqueue(self, upload_id: str) -> str:
        return self.store.enqueue(upload_id)

    # ---- worker side ----
    def run_one(self, worker: str) -> str | None:
        """Claim and process one job; returns its id, or None when the queue is empty."""
        c = self.store.claim(worker)
        if c is None:
            return None
        j = c.job
        self._emit(j, "parsing", STAGES["parsing"])
        try:
            self._pipeline(c)
        except IngestError as e:
            self._failed(j, e.code)
        except Exception:  # message may hold content: keep only a fixed code
            self._failed(j, "internal_error")
        return j.id

    def run_until_empty(self, worker: str) -> int:
        n = 0
        while self.run_one(worker):
            n += 1
        return n

    def _emit(self, j: JobRow, stage: str, pct: int) -> None:
        self.publish("ingestion.job.progressed", {"job_id": j.id, "workspace_id": j.workspace_id, "stage": stage, "pct": pct})

    def _failed(self, j: JobRow, code: str) -> None:
        state, _ = self.store.fail_attempt(j.id, code, self.max_attempts)
        if state == "failed":
            self.publish("ingestion.job.failed", {"job_id": j.id, "workspace_id": j.workspace_id,
                                                   "upload_id": j.upload_id, "error_code": code})

    def _pipeline(self, c: Claimed) -> None:
        j, st = c.job, self.store
        with self.open_upload(j.upload_id) as f:
            head = f.read(4096)
            name = ""
            adapter = self._detect(c.declared_format, name, head)
            st.set_format(j.id, adapter.kind, adapter.parser)
            f.seek(0)
            calls, lines, sessions, tasks, rejects = [], [], {}, {}, []
            for item in adapter.parse(f):
                if isinstance(item, registry.ParsedCall):
                    calls.append(item.call)
                    lines.append(item.line_no)
                elif isinstance(item, registry.ParsedReject):
                    rejects.append((item.line_no, item.code))
                elif isinstance(item, registry.ParsedSession):
                    sessions[item.key] = item.session
                elif isinstance(item, registry.ParsedTask):
                    tasks[item.key] = item.task
        st.advance(j.id, "normalizing", STAGES["normalizing"])
        self._emit(j, "normalizing", STAGES["normalizing"])
        src = self.get_source(j.workspace_id, c.source_id)
        project_id = getattr(src, "project_id", None) if src else None
        st.advance(j.id, "loading", STAGES["loading"])
        self._emit(j, "loading", STAGES["loading"])
        res = self.load_calls(j.workspace_id, project_id, c.source_id, j.id, calls, sessions, tasks) if calls else None
        if res is not None:
            rejects += [(lines[r["index"]], r["code"]) for r in res.rejected]
        counts = {"inserted": res.inserted if res else 0, "duplicates": res.duplicates if res else 0,
                  "rejected": len(rejects)}
        st.add_rejects(j.id, rejects)
        st.advance(j.id, "analyzing", STAGES["analyzing"], counts)
        self._emit(j, "analyzing", STAGES["analyzing"])
        st.finish(j.id, counts, len(calls) + len(rejects))
        self.publish("ingestion.job.finished", {"job_id": j.id, "workspace_id": j.workspace_id,
                                                 "upload_id": j.upload_id, "counts": counts})

    @staticmethod
    def _detect(declared: str | None, name: str, head: bytes):
        avail = registry.adapters()
        if declared:
            for a in avail:
                if a.kind == declared:
                    return a
        for a in avail:
            if a.detect(name, head):
                return a
        raise IngestError("unsupported_format")

    # ---- api side ----
    def get_job(self, ws: str, job_id: str) -> JobRow:
        j = self.store.job(ws, job_id)
        if j is None:
            raise IngestError("not_found", 404)
        return j

    def list_jobs(self, ws: str) -> list[JobRow]:
        return self.store.jobs(ws)

    def stream(self, ws: str, job_id: str, last_event_id: int = 0, heartbeat_s: float = 15.0, wait_s: float = 1.0,
               clock=time.monotonic):
        """Yield SSE text frames: replay from the store after last_event_id, then follow live. Ends after done/failed."""
        self.get_job(ws, job_id)
        last, beat = max(0, last_event_id), clock()
        while True:
            j = self.store.job(ws, job_id)
            evs = self.store.events_after(job_id, last)
            for e in evs:
                last = e.seq
                kind = e.stage if e.stage in TERMINAL else "progress"
                yield sse_frame(e, kind)
                if kind != "progress":
                    return
            if not evs:
                if j is None or j.state in TERMINAL:
                    return
                self.store.wait(job_id, last, wait_s)
                if clock() - beat >= heartbeat_s:
                    beat = clock()
                    yield ": heartbeat\n\n"


def sse_frame(e: EventRow, kind: str) -> str:
    import json

    data = json.dumps({"seq": e.seq, "stage": e.stage, "pct": e.pct, "counts": e.counts}, separators=(",", ":"))
    return f"id: {e.seq}\nevent: {kind}\ndata: {data}\n\n"

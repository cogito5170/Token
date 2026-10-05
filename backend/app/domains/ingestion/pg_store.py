"""PostgreSQL store. Claim is one UPDATE ... WHERE id = (SELECT ... FOR UPDATE SKIP LOCKED LIMIT 1), so two workers
never take one job. Every event row is written in the transaction that changes the job and is followed by NOTIFY."""
from __future__ import annotations

import json

from .service import MAX_REJECT_ROWS, Claimed, EventRow, IngestError, JobRow

COLS = ("id, workspace_id, upload_id, state, source_kind, parser, attempts, inserted, duplicates, rejected, "
        "last_error_code, created_at, finished_at")


def channel(job_id: str) -> str:
    return "ingest_job_" + job_id.replace("-", "")


def _job(r) -> JobRow:
    return JobRow(*[str(r[i]) if i in (0, 1, 2) else r[i] for i in range(13)])


class PgStore:
    def __init__(self, pool) -> None:
        self.pool = pool

    @staticmethod
    def _event(c, job_id, stage, pct, counts=None) -> int:
        c.execute("SELECT 1 FROM ingest_jobs WHERE id = %s FOR UPDATE", (job_id,))  # serializes seq per job
        seq = c.execute("SELECT COALESCE(MAX(seq), 0) + 1 FROM ingest_job_events WHERE job_id = %s", (job_id,)).fetchone()[0]
        c.execute("INSERT INTO ingest_job_events (job_id, seq, stage, pct, counts) VALUES (%s,%s,%s,%s,%s::jsonb)",
                  (job_id, seq, stage, pct, json.dumps(counts or {})))
        c.execute("SELECT pg_notify(%s, %s)", (channel(job_id), str(seq)))
        return seq

    def enqueue(self, upload_id):
        with self.pool.connection() as c:
            r = c.execute("SELECT workspace_id FROM uploads WHERE id = %s", (upload_id,)).fetchone()
            if r is None:
                raise IngestError("not_found", 404)
            live = c.execute("SELECT id FROM ingest_jobs WHERE upload_id = %s AND state NOT IN ('done','failed')",
                             (upload_id,)).fetchone()
            if live:
                return str(live[0])
            jid = str(c.execute("INSERT INTO ingest_jobs (workspace_id, upload_id) VALUES (%s,%s) RETURNING id",
                                (r[0], upload_id)).fetchone()[0])
            self._event(c, jid, "queued", 0)
            return jid

    def claim(self, worker):
        with self.pool.connection() as c:
            r = c.execute(
                "UPDATE ingest_jobs SET state='parsing', attempts=attempts+1, claimed_by=%s, claimed_at=now() "
                "WHERE id = (SELECT id FROM ingest_jobs WHERE state='queued' ORDER BY created_at "
                "FOR UPDATE SKIP LOCKED LIMIT 1) RETURNING " + COLS, (worker,)).fetchone()
            if r is None:
                return None
            self._event(c, str(r[0]), "parsing", 10)
            u = c.execute("SELECT source_id, declared_format FROM uploads WHERE id = %s", (r[2],)).fetchone()
            return Claimed(_job(r), str(u[0]), u[1])

    def advance(self, job_id, state, pct, counts=None):
        with self.pool.connection() as c:
            c.execute("UPDATE ingest_jobs SET state=%s WHERE id=%s", (state, job_id))
            return self._event(c, job_id, state, pct, counts)

    def set_format(self, job_id, kind, parser):
        with self.pool.connection() as c:
            c.execute("UPDATE ingest_jobs SET source_kind=%s, parser=%s WHERE id=%s", (kind, parser, job_id))

    def add_rejects(self, job_id, rejects):
        with self.pool.connection() as c:
            with c.cursor() as cur:
                cur.executemany("INSERT INTO ingest_rejects (job_id, line_no, error_code) VALUES (%s,%s,%s) "
                                "ON CONFLICT DO NOTHING", [(job_id, n, code) for n, code in rejects[:MAX_REJECT_ROWS]])

    def finish(self, job_id, counts, lines_total):
        with self.pool.connection() as c:
            c.execute("UPDATE ingest_jobs SET state='done', inserted=%s, duplicates=%s, rejected=%s, lines_total=%s, "
                      "finished_at=now() WHERE id=%s",
                      (counts["inserted"], counts["duplicates"], counts["rejected"], lines_total, job_id))
            return self._event(c, job_id, "done", 100, counts)

    def fail_attempt(self, job_id, code, max_attempts):
        with self.pool.connection() as c:
            n = c.execute("SELECT attempts FROM ingest_jobs WHERE id=%s FOR UPDATE", (job_id,)).fetchone()[0]
            if n < max_attempts:
                c.execute("UPDATE ingest_jobs SET state='queued', last_error_code=%s WHERE id=%s", (code, job_id))
                return "queued", self._event(c, job_id, "queued", 0)
            c.execute("UPDATE ingest_jobs SET state='failed', last_error_code=%s, finished_at=now() WHERE id=%s",
                      (code, job_id))
            return "failed", self._event(c, job_id, "failed", 0)

    def job(self, ws, job_id):
        try:
            with self.pool.connection() as c:
                r = c.execute("SELECT " + COLS + " FROM ingest_jobs WHERE id=%s AND workspace_id=%s", (job_id, ws)).fetchone()
        except Exception as e:
            if getattr(e, "sqlstate", "") == "22P02":  # malformed uuid
                return None
            raise
        return _job(r) if r else None

    def jobs(self, ws):
        with self.pool.connection() as c:
            return [_job(r) for r in c.execute("SELECT " + COLS + " FROM ingest_jobs WHERE workspace_id=%s "
                                               "ORDER BY created_at DESC LIMIT 200", (ws,)).fetchall()]

    def events_after(self, job_id, seq):
        with self.pool.connection() as c:
            return [EventRow(r[0], r[1], r[2], r[3]) for r in c.execute(
                "SELECT seq, stage, pct, counts FROM ingest_job_events WHERE job_id=%s AND seq>%s ORDER BY seq",
                (job_id, seq)).fetchall()]

    def wait(self, job_id, seq, timeout):
        """LISTEN until a NOTIFY or `timeout`; any failure degrades to the caller's polling interval."""
        import time

        try:
            with self.pool.connection() as c:
                c.autocommit = True
                c.execute(f"LISTEN {channel(job_id)}")
                if c.execute("SELECT 1 FROM ingest_job_events WHERE job_id=%s AND seq>%s LIMIT 1", (job_id, seq)).fetchone():
                    return
                for _ in c.notifies(timeout=timeout, stop_after=1):
                    return
        except Exception:
            time.sleep(timeout)

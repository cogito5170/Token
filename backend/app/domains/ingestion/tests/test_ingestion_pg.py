"""ingestion on a real PostgreSQL 16 (docs/schema.sql). Skipped without GC_SCHEMA_TEST_DSN, psql or psycopg."""
import io
import os
import shutil
import subprocess
import threading
import unittest
import uuid
from pathlib import Path

from .helpers import FakeAdapter, fake_get_upload

DSN = os.environ.get("GC_SCHEMA_TEST_DSN")
REPO = Path(__file__).resolve().parents[5]
try:
    import psycopg  # noqa: F401
    import psycopg_pool
except ImportError:
    psycopg = None

GOOD = b"FAKE\nclaude-sonnet-5-5,10,5\n!junk\nno-such-model,1,1\n"


@unittest.skipUnless(DSN and shutil.which("psql") and psycopg, "GC_SCHEMA_TEST_DSN, psql or psycopg missing")
class PgIngestTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.name = "gc_ingest_" + uuid.uuid4().hex[:8]
        run = lambda dsn, *a: subprocess.run(["psql", dsn, "-v", "ON_ERROR_STOP=1", "-qAt", *a],  # noqa: E731
                                              capture_output=True, text=True, timeout=120)
        assert run(DSN, "-c", f"CREATE DATABASE {cls.name}").returncode == 0
        cls.dsn = DSN.rsplit("/", 1)[0] + "/" + cls.name
        r = run(cls.dsn, "-f", str(REPO / "docs" / "schema.sql"))
        assert r.returncode == 0, r.stderr
        cls.pool = psycopg_pool.ConnectionPool(cls.dsn, min_size=1, max_size=12, open=True)
        with cls.pool.connection() as c:
            u = c.execute("INSERT INTO users (email, display_name, password_hash) VALUES ('a@example.com','a','x') RETURNING id").fetchone()[0]
            cls.ws = str(c.execute("INSERT INTO workspaces (name, slug, created_by) VALUES ('w','w',%s) RETURNING id", (u,)).fetchone()[0])
            cls.src = str(c.execute("INSERT INTO sources (workspace_id, kind, name) VALUES (%s,'upload','s') RETURNING id", (cls.ws,)).fetchone()[0])
            cls.user = u

    @classmethod
    def tearDownClass(cls):
        from app.core import db
        db._pool = None
        cls.pool.close()
        subprocess.run(["psql", DSN, "-qAt", "-c", f"DROP DATABASE IF EXISTS {cls.name}"], capture_output=True)

    def _upload(self, n=1):
        ids = []
        with self.pool.connection() as c:
            for i in range(n):
                ids.append(str(c.execute(
                    "INSERT INTO uploads (workspace_id, source_id, uploaded_by, filename, size_bytes, sha256, storage_path) "
                    "VALUES (%s,%s,%s,'f',1,%s,'p') RETURNING id", (self.ws, self.src, self.user, uuid.uuid4().hex)).fetchone()[0]))
        return ids

    def _svc(self, files, usage_svc=None):
        from app.domains.ingestion import registry
        from app.domains.ingestion.pg_store import PgStore
        from app.domains.ingestion.service import IngestService
        from app.core import db
        from app.domains.usage.api import load_calls

        db._pool = self.pool  # usage.api resolves its service from the shared pool
        registry.register(FakeAdapter())
        self.addCleanup(registry.unregister, "claude_code")
        return IngestService(PgStore(self.pool), lambda uid: io.BytesIO(files[uid]),
                             fake_get_upload(files, self.ws, self.src), load_calls, lambda w, s: None)

    def test_two_workers_never_claim_one_job_and_pipeline_persists(self):
        ups = self._upload(12)
        svc = self._svc({u: GOOD.replace(b"10,5", f"{i + 1},5".encode()) for i, u in enumerate(ups)})
        jobs = {svc.enqueue(u) for u in ups}
        done, lock = [], threading.Lock()

        def work(name):
            while True:
                j = svc.run_one(name)
                if j is None:
                    return
                with lock:
                    done.append(j)

        ts = [threading.Thread(target=work, args=(f"w{i}",)) for i in range(4)]
        [t.start() for t in ts]
        [t.join() for t in ts]
        self.assertEqual(sorted(done), sorted(jobs))  # each job exactly once
        with self.pool.connection() as c:
            self.assertEqual(c.execute("SELECT count(*) FROM ingest_jobs WHERE id = ANY(%s::uuid[]) AND attempts = 1 AND state='done'",
                                       (list(jobs),)).fetchone()[0], 12)
        jid = next(iter(jobs))
        j = svc.get_job(self.ws, jid)
        self.assertEqual((j.inserted, j.rejected), (1, 2))
        frames = list(svc.stream(self.ws, jid))
        self.assertEqual(len([f for f in frames if f.startswith("id: ")]), 6)
        self.assertEqual([f.split("\n")[0] for f in svc.stream(self.ws, jid, 4)], ["id: 5", "id: 6"])
        with self.pool.connection() as c:
            self.assertEqual(c.execute("SELECT count(*) FROM ingest_rejects WHERE job_id=%s", (jid,)).fetchone()[0], 2)

    def test_failed_job_code_only_and_notify(self):
        up = self._upload()[0]
        svc = self._svc({up: b"FAKE\nBOOM\n"})
        jid = svc.enqueue(up)
        svc.run_until_empty("w")
        j = svc.get_job(self.ws, jid)
        self.assertEqual((j.state, j.attempts, j.last_error_code), ("failed", 3, "internal_error"))
        with self.pool.connection() as c:
            rows = c.execute("SELECT stage, counts::text FROM ingest_job_events WHERE job_id=%s", (jid,)).fetchall()
        self.assertNotIn("sk-ant", repr(rows))
        self.assertEqual(rows[-1][0], "failed")

    def test_wait_wakes_on_notify(self):
        up = self._upload()[0]
        svc = self._svc({up: GOOD})
        jid = svc.enqueue(up)
        got = []
        t = threading.Thread(target=lambda: (svc.store.wait(jid, 1, 10.0), got.append(1)))
        t.start()
        import time
        time.sleep(0.5)
        t0 = time.monotonic()
        svc.run_one("w")
        t.join(5)
        self.assertEqual(got, [1])
        self.assertLess(time.monotonic() - t0, 3)

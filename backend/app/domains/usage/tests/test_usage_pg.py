"""usage on a real PostgreSQL 16 (docs/schema.sql). Skipped without GC_SCHEMA_TEST_DSN, psql or psycopg."""
import json
import os
import shutil
import subprocess
import unittest
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

DSN = os.environ.get("GC_SCHEMA_TEST_DSN")
REPO = Path(__file__).resolve().parents[5]
try:
    import psycopg
    import psycopg_pool
except ImportError:
    psycopg = None

T0 = datetime(2026, 3, 1, 12, 0, tzinfo=timezone.utc)


@unittest.skipUnless(DSN and shutil.which("psql") and psycopg, "GC_SCHEMA_TEST_DSN, psql or psycopg missing")
class PgUsageTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.name = "gc_usage_" + uuid.uuid4().hex[:8]
        run = lambda dsn, *a: subprocess.run(["psql", dsn, "-v", "ON_ERROR_STOP=1", "-qAt", *a],  # noqa: E731
                                              capture_output=True, text=True, timeout=120)
        r = run(DSN, "-c", f"CREATE DATABASE {cls.name}")
        assert r.returncode == 0, r.stderr
        cls.dsn = DSN.rsplit("/", 1)[0] + "/" + cls.name
        r = run(cls.dsn, "-f", str(REPO / "docs" / "schema.sql"))
        assert r.returncode == 0, r.stderr
        cls.pool = psycopg_pool.ConnectionPool(cls.dsn, min_size=1, max_size=3, open=True)
        with cls.pool.connection() as c:
            u = c.execute("INSERT INTO users (email, display_name, password_hash) VALUES ('a@example.com','a','x') RETURNING id").fetchone()[0]
            cls.ws = str(c.execute("INSERT INTO workspaces (name, slug, created_by) VALUES ('w','w',%s) RETURNING id",
                                   (u,)).fetchone()[0])
            cls.src = str(c.execute("INSERT INTO sources (workspace_id, kind, name) "
                                    "VALUES (%s,'upload','s') RETURNING id", (cls.ws,)).fetchone()[0])
            up = c.execute("INSERT INTO uploads (workspace_id, source_id, uploaded_by, filename, size_bytes, sha256, "
                           "storage_path) VALUES (%s,%s,%s,'f',1,'h','p') RETURNING id", (cls.ws, cls.src, u)).fetchone()[0]
            cls.job = str(c.execute("INSERT INTO ingest_jobs (workspace_id, upload_id) VALUES (%s,%s) RETURNING id",
                                    (cls.ws, up)).fetchone()[0])

    @classmethod
    def tearDownClass(cls):
        cls.pool.close()
        subprocess.run(["psql", DSN, "-qAt", "-c", f"DROP DATABASE IF EXISTS {cls.name}"], capture_output=True)

    def test_cost_idempotent_reload_and_nulls(self):
        from app.domains.usage.pg_store import PgStore, seed
        from app.domains.usage.service import CallIn, TaskIn, UsageService

        seed(self.pool)
        seed(self.pool)  # idempotent
        svc = UsageService(PgStore(self.pool), now=lambda: T0 + timedelta(days=1))
        rows = [json.loads(l) for l in (REPO / "fixtures/final_task/ledger.jsonl").read_text().splitlines() if l.strip()]
        calls = [CallIn(r["model"], "anthropic", "ga_l0", T0 + timedelta(seconds=i), f"ledger-{i}",
                        input_tokens=r["usage"]["input_tokens"], cache_read_tokens=r["usage"]["cache_read_input_tokens"],
                        cache_write_5m_tokens=r["usage"]["cache_creation_input_tokens"],
                        output_tokens=r["usage"]["output_tokens"], session=r["run_id"], task=r["run_id"])
                 for i, r in enumerate(rows)]
        calls.append(CallIn("claude-sonnet-5-5", "anthropic", "otel", T0, "nulls"))
        res = svc.load_calls(self.ws, None, self.src, self.job, calls, tasks={rows[0]["run_id"]: TaskIn(outcome="correct")})
        self.assertEqual((res.inserted, res.duplicates), (len(calls), 0))
        with self.pool.connection() as c:
            got = c.execute("SELECT dedupe_key, cost_list_nanousd FROM usage_calls WHERE workspace_id=%s",
                            (self.ws,)).fetchall()
            for k, nano in got:
                if k == "nulls":
                    self.assertIsNone(nano)
                else:
                    r = rows[int(k.split("-")[1])]
                    self.assertLessEqual(abs(nano / 1000 - round(r["quota_usd"] * 1e6)), 1)
            before = c.execute("SELECT count(*), sum(calls), sum(cost_list_microusd) FROM usage_daily "
                               "WHERE workspace_id=%s", (self.ws,)).fetchone()
            tb = c.execute("SELECT sum(calls), sum(cost_list_nanousd) FROM usage_tasks WHERE workspace_id=%s",
                           (self.ws,)).fetchone()
        again = svc.load_calls(self.ws, None, self.src, self.job, calls)
        self.assertEqual((again.inserted, again.duplicates), (0, len(calls)))
        with self.pool.connection() as c:
            self.assertEqual(before, c.execute("SELECT count(*), sum(calls), sum(cost_list_microusd) FROM usage_daily "
                                               "WHERE workspace_id=%s", (self.ws,)).fetchone())
            self.assertEqual(tb, c.execute("SELECT sum(calls), sum(cost_list_nanousd) FROM usage_tasks "
                                           "WHERE workspace_id=%s", (self.ws,)).fetchone())
        s = svc.summary(self.ws)
        self.assertEqual(s["tiles"]["total_tokens"]["unit"], "tokens")
        self.assertIsNone(s["tiles"]["cost_cli"]["value"])
        self.assertGreater(s["tiles"]["cost_list"]["value"], 0)
        self.assertTrue(svc.call_size(self.ws, threshold=100000)["outliers"])
        self.assertEqual(svc.compare(self.ws, ["model"])["dims"], ["model"])
        pg = svc.call_page(self.ws, limit=10)
        self.assertEqual(len(pg["items"]), 10)
        tid = svc.task_page(self.ws, limit=1)["items"][0]["id"]
        self.assertEqual(svc.update_task(self.ws, "u", tid, outcome="incorrect")["outcome"], "incorrect")


if __name__ == "__main__":
    unittest.main()

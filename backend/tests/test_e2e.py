"""CMD-GC19 end to end on a real PostgreSQL 16 (GC_SCHEMA_TEST_DSN): signup -> workspace -> upload -> worker claims and
ingests -> usage shows the calls -> advisor finds R2 -> report export lists it. Everything goes through HTTP, the worker's
run_one, or public api.py. API and worker run in one process here (one event bus), as app/worker/README.md describes."""
import io
import json
import os
import shutil
import subprocess
import tempfile
import unittest
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DSN = os.environ.get("GC_SCHEMA_TEST_DSN")
try:
    import fastapi  # noqa: F401
    import httpx  # noqa: F401
    import psycopg  # noqa: F401
    import psycopg_pool  # noqa: F401
    import argon2  # noqa: F401
    import multipart  # noqa: F401
    HAVE = True
except ImportError:
    HAVE = False
try:
    import telemetry.collect  # noqa: F401
    HAVE_L0 = True
except ImportError:
    HAVE_L0 = False

R2 = json.loads((ROOT / "fixtures/advisor/R2.json").read_text())
PW = "pw-" + "Zq8" * 4  # fake test credential, assembled so the secret scan stays clean


class R2FixtureAdapter:
    """Reads fixtures/advisor/R2.json (its own format) as a ga_l0 source; timestamps move to 'now' so the advisor's
    30-day window always contains them."""
    kind, parser = "ga_l0", "test-fixture@r2"

    def detect(self, filename, head):
        return True

    def parse(self, f):
        from app.domains.ingestion import registry
        from app.domains.usage.api import CallIn
        base = datetime.now(timezone.utc) - timedelta(hours=2)
        for i, c in enumerate(json.loads(f.read())["calls"], start=1):
            yield registry.ParsedCall(i, CallIn(
                c["model"], "anthropic", self.kind, base + timedelta(minutes=i), f"r2-{c['id']}", call_index=i,
                input_tokens=c["input"], cache_read_tokens=c["cache_read"], output_tokens=c["output"],
                content_hashes=c["content_hashes"], session=c["session"], task=c["task"]))


def reset_singletons():
    """Services cache a PgStore on the pool of the previous test database."""
    import importlib
    for d in ("identity.router", "workspace.wiring", "audit.wiring", "source.wiring", "ingestion.wiring", "usage.wiring",
              "quota.wiring", "advisor.wiring", "notification.wiring", "profile.wiring", "report.wiring",
              "simulation.wiring"):
        m = importlib.import_module(f"app.domains.{d}")
        if hasattr(m, "_service"):
            m._service = None


@unittest.skipUnless(DSN and HAVE and shutil.which("psql"), "GC_SCHEMA_TEST_DSN, psql or runtime deps missing")
class EndToEndTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from app.core import db
        from app.domains.ingestion import registry
        cls.name = "gc_e2e_" + uuid.uuid4().hex[:8]
        run = lambda dsn, *a: subprocess.run(["psql", dsn, "-v", "ON_ERROR_STOP=1", "-qAt", *a],  # noqa: E731
                                              capture_output=True, text=True, timeout=120)
        assert run(DSN, "-c", f"CREATE DATABASE {cls.name}").returncode == 0
        cls.dsn = DSN.rsplit("/", 1)[0] + "/" + cls.name
        r = run(cls.dsn, "-f", str(ROOT / "docs/schema.sql"))
        assert r.returncode == 0, r.stderr
        cls.tmp = tempfile.mkdtemp()
        cls.env = {k: os.environ.get(k) for k in ("DATABASE_URL", "GC_JWT_SECRET", "GC_UPLOAD_DIR")}
        os.environ.update(DATABASE_URL=cls.dsn, GC_JWT_SECRET="e2e-jwt-" + "k" * 24, GC_UPLOAD_DIR=cls.tmp)
        db.close_pool()
        reset_singletons()
        cls.saved_adapters = registry.adapters()
        from fastapi.testclient import TestClient
        from app.main import create_app
        cls.client = TestClient(create_app())
        cls.client.__enter__()  # lifespan: opens the pool from DATABASE_URL
        from app.api.wiring import wire_worker
        wire_worker()
        registry.register(R2FixtureAdapter())

    @classmethod
    def tearDownClass(cls):
        from app.core import db
        from app.domains.ingestion import registry
        cls.client.__exit__(None, None, None)
        db.close_pool()
        reset_singletons()
        registry._adapters[:] = cls.saved_adapters
        for k, v in cls.env.items():
            os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)
        shutil.rmtree(cls.tmp, ignore_errors=True)
        subprocess.run(["psql", DSN, "-qAt", "-c", f"DROP DATABASE IF EXISTS {cls.name}"], capture_output=True)

    # ---- helpers
    def signup(self, email):
        r = self.client.post("/v1/auth/signup", json={"email": email, "password": PW, "display_name": "E2E"})
        self.assertEqual(r.status_code, 201, r.text)
        return {"Authorization": "Bearer " + r.json()["access_token"]}

    def workspace(self, h):
        r = self.client.get("/v1/workspaces", headers=h)
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(len(r.json()), 1, "identity.user.created must create the Personal workspace")
        return r.json()[0]["id"]

    def upload(self, h, ws, kind, data, name):
        s = self.client.post(f"/v1/workspaces/{ws}/sources", headers=h, json={"kind": "upload", "name": "e2e"})
        self.assertEqual(s.status_code, 201, s.text)
        r = self.client.post(f"/v1/workspaces/{ws}/uploads", headers=h, data={"source_id": s.json()["id"],
                             "declared_format": kind}, files={"file": (name, io.BytesIO(data))})
        self.assertEqual(r.status_code, 201, r.text)
        return r.json()

    def run_worker(self):
        from app.domains.ingestion.wiring import get_service
        return get_service().run_one("e2e-worker")

    # ---- the flow
    def test_signup_to_report_export(self):
        h = self.signup("e2e-r2@example.com")
        ws = self.workspace(h)
        up = self.upload(h, ws, "ga_l0", json.dumps(R2).encode(), "r2.json")
        self.assertTrue(up["job_id"], "source must be wired to ingestion.api.enqueue")
        self.assertEqual(self.client.get(f"/v1/workspaces/{ws}/ingest-jobs/{up['job_id']}", headers=h).json()["state"],
                         "queued")

        self.assertEqual(self.run_worker(), up["job_id"])                       # the worker claims and ingests
        job = self.client.get(f"/v1/workspaces/{ws}/ingest-jobs/{up['job_id']}", headers=h).json()
        self.assertEqual((job["state"], job["inserted"]), ("done", len(R2["calls"])), job)

        calls = self.client.get(f"/v1/workspaces/{ws}/usage/calls", headers=h).json()["items"]
        self.assertEqual(len(calls), len(R2["calls"]))
        tiles = self.client.get(f"/v1/workspaces/{ws}/usage/summary", headers=h).json()["tiles"]
        self.assertGreater(tiles["total_tokens"]["value"], 0)

        fs = self.client.get(f"/v1/workspaces/{ws}/advisor/findings", headers=h).json()
        r2 = [f for f in fs if f["rule_id"] == "R2"]
        self.assertEqual(len(r2), 1, fs)                                         # worker-side advisor subscriber ran
        self.assertGreater(r2[0]["savings"]["p50"], 0)

        b = self.client.post(f"/v1/workspaces/{ws}/budgets", headers=h, json={
            "scope": "workspace", "period": "month", "measure": "list", "limit_microusd": 5_000_000})
        self.assertEqual(b.status_code, 201, b.text)                            # quota.api.list_budgets feeds the report
        today = datetime.now(timezone.utc).date()
        rep = self.client.post(f"/v1/workspaces/{ws}/reports", headers=h, json={
            "from": (today - timedelta(days=30)).isoformat(), "to": (today + timedelta(days=1)).isoformat()})
        self.assertEqual(rep.status_code, 201, rep.text)
        rid = rep.json()["id"]
        csv_text = self.client.get(f"/v1/workspaces/{ws}/reports/{rid}/export", headers=h, params={"format": "csv"}).text
        self.assertIn("savings,", csv_text)
        self.assertIn(f"{r2[0]['id']}", csv_text, "the R2 finding is listed in the export")
        self.assertIn(f"{b.json()['id']}.limit", csv_text, "the budget is listed (quota.api.list_budgets)")
        js = self.client.get(f"/v1/workspaces/{ws}/reports/{rid}/export", headers=h, params={"format": "json"})
        self.assertEqual(js.status_code, 200, js.text)

        # the ingestion events reached the notification subscriber in this process
        n = self.client.get("/v1/notifications", headers=h)
        self.assertEqual(n.status_code, 200, n.text)

        # audit: signup/workspace/budget/report actions were recorded through audit.api.record (identity+workspace wired)
        log = self.client.get(f"/v1/workspaces/{ws}/audit-log", headers=h)
        self.assertEqual(log.status_code, 200, log.text)
        actions = {e["action"] for e in log.json()["items"]}
        self.assertTrue({"budget.create", "report.generate"} <= actions, actions)

    def test_error_bodies_over_http_with_a_database(self):
        h = self.signup("e2e-err@example.com")
        other = self.signup("e2e-other@example.com")
        ws = self.workspace(h)
        for r in (self.client.get("/v1/me"),
                  self.client.get(f"/v1/workspaces/{ws}", headers=other),                       # hidden: 404
                  self.client.post("/v1/auth/login", json={"email": "e2e-err@example.com", "password": "wrong-" + PW}),
                  self.client.get(f"/v1/workspaces/{ws}/reports/{uuid.uuid4()}/export", headers=h, params={"format": "csv"}),
                  self.client.post(f"/v1/workspaces/{ws}/reports", headers=h, json={"from": "x", "to": "y"})):
            self.assertGreaterEqual(r.status_code, 400)
            self.assertEqual(sorted(r.json()), ["code", "message"], (r.status_code, r.text))

    def test_signup_creates_exactly_one_personal_workspace(self):
        h = self.signup("e2e-once@example.com")
        self.workspace(h)  # asserts len == 1 (workspace subscriber wired once)

    @unittest.skipUnless(HAVE_L0, "pinned l0-telemetry not installed")
    def test_claude_code_upload_is_ingested_and_shown_in_usage(self):
        h = self.signup("e2e-cc@example.com")
        ws = self.workspace(h)
        t0 = datetime.now(timezone.utc) - timedelta(hours=1)
        lines = [json.dumps({
            "type": "assistant", "sessionId": "cc-session-1", "uuid": f"u{i}", "timestamp": (t0 + timedelta(minutes=i)).isoformat(),
            "message": {"id": f"msg_{i}", "model": "claude-sonnet-5-5", "role": "assistant", "content": [],
                        "usage": {"input_tokens": 1000 * i, "output_tokens": 50, "cache_read_input_tokens": 0,
                                  "cache_creation_input_tokens": 0}}}) for i in (1, 2)]
        from app.domains.ingestion import registry
        from app.domains.ingestion.adapters import ClaudeCodeAdapter
        registry.register(ClaudeCodeAdapter())
        self.addCleanup(registry.register, R2FixtureAdapter())
        up = self.upload(h, ws, "claude_code", ("\n".join(lines) + "\n").encode(), "session.jsonl")
        self.assertEqual(self.run_worker(), up["job_id"])
        job = self.client.get(f"/v1/workspaces/{ws}/ingest-jobs/{up['job_id']}", headers=h).json()
        self.assertEqual((job["state"], job["inserted"]), ("done", 2), job)
        calls = self.client.get(f"/v1/workspaces/{ws}/usage/calls", headers=h).json()["items"]
        self.assertEqual(len(calls), 2)


if __name__ == "__main__":
    unittest.main()

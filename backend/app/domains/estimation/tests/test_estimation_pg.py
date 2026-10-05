"""estimation over HTTP on a real PostgreSQL 16 (docs/schema.sql). Skipped without GC_SCHEMA_TEST_DSN, psql, psycopg or
fastapi. The description text must never reach the database."""
import hashlib
import os
import shutil
import subprocess
import unittest
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

DSN = os.environ.get("GC_SCHEMA_TEST_DSN")
REPO = Path(__file__).resolve().parents[5]
try:
    import psycopg  # noqa: F401
    import psycopg_pool
    from fastapi import FastAPI, HTTPException
    from fastapi.testclient import TestClient
    HAVE = True
except ImportError:
    HAVE = False

SECRET = "rewrite the payroll export so the quarterly bonus is hidden from audit"
RANK = {"viewer": 0, "developer": 1, "admin": 2}


@unittest.skipUnless(DSN and shutil.which("psql") and HAVE, "GC_SCHEMA_TEST_DSN, psql, psycopg or fastapi missing")
class EstimationHttpPgTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from app.core import db
        # the usage service singleton binds to the pool it first sees: give this class its own, restore on teardown
        cls.usage_patch = mock.patch("app.domains.usage.wiring._service", None)
        cls.usage_patch.start()
        cls.name = "gc_est_" + uuid.uuid4().hex[:8]
        run = lambda dsn, *a: subprocess.run(["psql", dsn, "-v", "ON_ERROR_STOP=1", "-qAt", *a],  # noqa: E731
                                              capture_output=True, text=True, timeout=120)
        assert run(DSN, "-c", f"CREATE DATABASE {cls.name}").returncode == 0
        cls.dsn = DSN.rsplit("/", 1)[0] + "/" + cls.name
        r = run(cls.dsn, "-f", str(REPO / "docs" / "schema.sql"))
        assert r.returncode == 0, r.stderr
        cls.pool = db.open_pool(cls.dsn)
        with cls.pool.connection() as c:
            cls.user = str(c.execute("INSERT INTO users (email, display_name, password_hash) VALUES "
                                     "('e@example.com','e','x') RETURNING id").fetchone()[0])
            mk = lambda n: str(c.execute("INSERT INTO workspaces (name, slug, created_by) VALUES (%s,%s,%s) "  # noqa: E731
                                         "RETURNING id", (n, n, cls.user)).fetchone()[0])
            cls.ws, cls.other_ws = mk("w1"), mk("w2")
            c.execute("INSERT INTO models (id, provider, family, tier, min_cache_tokens, display_name) "
                      "VALUES ('m-a','anthropic','claude',2,1,'m-a')")
            now = datetime.now(timezone.utc)
            cls.task_ids = []
            for i in range(4):
                cls.task_ids.append(str(c.execute(
                    "INSERT INTO usage_tasks (workspace_id, kind, structure, context_mode, model_primary, outcome, "
                    "started_at, calls, input_tokens, cache_read_tokens, cache_write_tokens, output_tokens, "
                    "cost_list_nanousd) VALUES (%s,'feature','single','selective','m-a','correct',%s,3,%s,0,0,%s,%s) "
                    "RETURNING id", (cls.ws, now - timedelta(days=i), 1000 * (i + 1), 500, 2_000_000 * (i + 1))
                ).fetchone()[0]))

    @classmethod
    def tearDownClass(cls):
        from app.core import db
        db.close_pool()
        cls.usage_patch.stop()
        subprocess.run(["psql", DSN, "-qAt", "-c", f"DROP DATABASE {cls.name} WITH (FORCE)"], capture_output=True)

    def setUp(self):
        from app.api import errors
        from app.domains.estimation import api, router
        from app.domains.identity.api import current_user
        api.set_service(None)
        self.addCleanup(api.set_service, None)
        self.role, self.calls = "developer", []

        def require_member(ws, uid, min_role="viewer"):
            self.calls.append((ws, min_role))
            if ws not in (self.ws,):
                raise HTTPException(404, detail={"code": "not_found", "message": "workspace not found"})
            if RANK[self.role] < RANK[min_role]:
                raise HTTPException(403, detail={"code": "forbidden", "message": "requires role " + min_role})

        p = mock.patch.object(router, "require_member", require_member)
        p.start()
        self.addCleanup(p.stop)
        app = FastAPI()
        errors.install(app)
        app.include_router(router.router)
        app.dependency_overrides[current_user] = lambda: SimpleNamespace(id=self.user)
        self.c = TestClient(app)
        self.base = f"/v1/workspaces/{self.ws}"

    def create(self, **over):
        body = {"description": SECRET, "task_kind": "feature", "model": "m-a", "structure": "single",
                "context_mode": "selective", "repo_size_loc": 5000, "language": "python"}
        body.update(over)
        return self.c.post(self.base + "/estimates", json=body)

    def test_create_get_list_roundtrip_with_workspace_evidence(self):
        r = self.create()
        self.assertEqual(r.status_code, 201, r.text)
        est = r.json()
        for q in ("input_tokens", "cache_tokens", "output_tokens", "cost_list", "calls"):
            rg = est[q]
            self.assertLessEqual(rg["p10"], rg["p50"])
            self.assertLessEqual(rg["p50"], rg["p90"])
            self.assertEqual(rg["provenance"], "ESTIMATED")
        self.assertEqual(est["input_tokens"]["unit"], "tokens")
        self.assertEqual(est["cost_list"]["unit"], "microusd")
        self.assertEqual(est["success_prob"]["unit"], "permille")
        self.assertEqual(est["estimator"], {"version": 1, "mape_permille": None})
        self.assertEqual(est["evidence"]["basis"], "blended")
        self.assertEqual(sorted(est["evidence"]["task_ids"]), sorted(self.task_ids))
        self.assertGreater(est["evidence"]["n"], len(self.task_ids))  # + global prior runs
        got = self.c.get(f"{self.base}/estimates/{est['id']}")
        self.assertEqual(got.status_code, 200)
        self.assertEqual(got.json(), est)
        self.assertIn(est["id"], [e["id"] for e in self.c.get(self.base + "/estimates").json()])

    def test_description_text_never_reaches_the_database(self):
        est = self.create().json()
        with self.pool.connection() as c:
            for t in ("estimates", "estimate_evidence", "estimate_outcomes", "estimator_models"):
                for (txt,) in c.execute(f"SELECT x::text FROM {t} x").fetchall():
                    for word in ("payroll", "bonus", "audit"):
                        self.assertNotIn(word, txt, t)
            req = c.execute("SELECT request, features FROM estimates WHERE id=%s", (est["id"],)).fetchone()
        self.assertEqual(req[0]["description"], {"sha256": hashlib.sha256(SECRET.encode()).hexdigest(),
                                                 "len": len(SECRET)})
        self.assertEqual(req[1]["description_len"], len(SECRET))

    def test_accuracy_roundtrip_from_a_recorded_outcome(self):
        from app.domains.estimation import api
        a0 = self.c.get(self.base + "/estimation/accuracy").json()
        n0 = a0["n"]
        est = self.create(model="m-a").json()
        total = sum(est[q]["p50"] for q in ("input_tokens", "cache_tokens", "output_tokens"))
        actual = {"total_tokens": total * 100, "cost_list_microusd": est["cost_list"]["p50"]}
        api.record_outcome(est["id"], actual, self.ws, self.task_ids[0])
        acc = self.c.get(self.base + "/estimation/accuracy").json()
        self.assertEqual(acc["n"], n0 + 1)
        self.assertIsNotNone(acc["mape_tokens"]["value"])
        self.assertEqual(acc["mape_tokens"]["unit"], "permille")
        self.assertEqual(acc["series"]["bucket"], "day")
        # the window is honoured: nothing recorded in the future
        future = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()
        res = self.c.get(self.base + "/estimation/accuracy", params={"from": future})
        self.assertEqual(res.json()["n"], 0)
        self.assertIsNone(res.json()["mape_tokens"]["value"])  # unknown is null, never 0
        with self.pool.connection() as c:
            row = c.execute("SELECT ape_tokens_permille, within_p10_p90 FROM estimate_outcomes WHERE estimate_id=%s",
                            (est["id"],)).fetchone()
        self.assertEqual(row[0], 990)  # actual = 100 x p50 -> |y - p50| / y = 0.99
        self.assertFalse(row[1])

    def test_unknown_malformed_and_foreign_ids_are_404(self):
        mine = self.create().json()["id"]
        for bad in ("abc", str(uuid.uuid4())):
            r = self.c.get(f"{self.base}/estimates/{bad}")
            self.assertEqual((r.status_code, r.json()["code"]), (404, "not_found"), bad)
        self.assertEqual(self.c.get(f"/v1/workspaces/{self.other_ws}/estimates/{mine}").status_code, 404)
        with self.pool.connection() as c:  # the estimate exists, but another workspace's id must not reach it
            self.assertEqual(c.execute("SELECT count(*) FROM estimates WHERE id=%s", (mine,)).fetchone()[0], 1)
        from app.domains.estimation import api
        self.assertIsNone(api.get_service().get(self.other_ws, mine))

    def test_roles_create_needs_developer_reads_need_member(self):
        self.role = "viewer"
        self.assertEqual(self.create().status_code, 403)
        self.assertEqual(self.c.get(self.base + "/estimates").status_code, 200)
        self.assertEqual(self.c.get(self.base + "/estimation/accuracy").status_code, 200)
        self.assertEqual(self.c.get(f"{self.base}/estimates/{uuid.uuid4()}").status_code, 404)
        self.assertEqual(self.calls, [(self.ws, "developer"), (self.ws, "viewer"), (self.ws, "viewer"),
                                      (self.ws, "viewer")])
        self.assertEqual(self.c.post(f"/v1/workspaces/{self.other_ws}/estimates", json={}).status_code, 404)

    def test_request_validation_gives_422_code_message(self):
        n = lambda: self.c.get(self.base + "/estimates").json()  # noqa: E731
        before = len(n())
        for over in ({"task_kind": "k"}, {"model": ""}, {"structure": "Z"}, {"context_mode": "x"},
                     {"description": "x" * 20001}, {"repo_size_loc": -1}, {"description": None}):
            r = self.create(**over)
            self.assertEqual(r.status_code, 422, over)
            self.assertEqual(sorted(r.json()), ["code", "message"])
        self.assertEqual(self.c.post(self.base + "/estimates", json={"model": "m-a"}).status_code, 422)
        self.assertEqual(len(n()), before)
        self.assertEqual(self.create(description="x" * 20000).status_code, 201)

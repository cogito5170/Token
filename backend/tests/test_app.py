"""CMD-GC19: create_app() assembly (routes == openapi), error bodies, process wiring, quota.api.list_budgets.
No database needed; skipped without fastapi/httpx."""
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
try:
    import fastapi  # noqa: F401
    import httpx  # noqa: F401
    import yaml
    HAVE = True
except ImportError:
    HAVE = False

# Domains whose router.py does not exist yet (integration: not built). Paths marked `x-later: true` in the spec are
# not served by any domain. Building one makes this stale and the test fails: remove it here when its router is mounted.
UNBUILT = {"integration"}
METHODS = ("get", "post", "put", "patch", "delete")


def spec_routes():
    spec = yaml.safe_load((ROOT / "docs/api/openapi.yaml").read_text())
    return {(p, m.upper()): v["x-domain"] for p, v in spec["paths"].items() for m in v
            if m in METHODS and not v.get("x-later")}


def later_routes():
    spec = yaml.safe_load((ROOT / "docs/api/openapi.yaml").read_text())
    return {(p, m.upper()) for p, v in spec["paths"].items() for m in v if m in METHODS and v.get("x-later")}


@unittest.skipUnless(HAVE, "fastapi/httpx/pyyaml missing")
class AssemblyTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from app.domains.identity import router as identity
        from app.domains.identity.service import IdentityService, MemoryStore
        from app.main import create_app
        cls.app = create_app()
        svc = IdentityService(MemoryStore(), object(), "unit-test-jwt-" + "k" * 24)  # no database in this class
        cls.app.dependency_overrides[identity.get_service] = lambda: svc

    def test_routes_equal_openapi_except_unbuilt_domains(self):
        want = spec_routes()
        got = {(p, m.upper()) for p, v in self.app.openapi()["paths"].items() for m in v}
        self.assertEqual(sorted(got - set(want)), [("/healthz", "GET")], "extra routes")
        missing = {k: d for k, d in want.items() if k not in got}
        self.assertEqual({d for d in missing.values()}, UNBUILT, f"missing routes: {sorted(missing)}")
        built = {d for d in want.values()} - UNBUILT
        self.assertEqual({d for k, d in want.items() if k in got}, built)

    def test_x_later_paths_are_not_served(self):
        later = later_routes()
        self.assertTrue(later, "the spec has no x-later paths any more: drop this test")
        got = {(p, m.upper()) for p, v in self.app.openapi()["paths"].items() for m in v}
        self.assertEqual(sorted(got & later), [])

    def test_estimation_and_run_are_mounted(self):
        want = spec_routes()
        got = {(p, m.upper()) for p, v in self.app.openapi()["paths"].items() for m in v}
        for dom in ("estimation", "run"):
            routes = {k for k, d in want.items() if d == dom}
            self.assertTrue(routes, dom)
            self.assertEqual(sorted(routes - got), [], dom)

    def test_every_built_domain_is_mounted_including_simulation(self):
        paths = set(self.app.openapi()["paths"])
        self.assertIn("/v1/workspaces/{ws}/simulations", paths)
        self.assertIn("/v1/workspaces/{ws}/reports", paths)

    def test_error_bodies_are_code_message_at_top_level(self):
        from fastapi.testclient import TestClient
        c = TestClient(self.app)
        for r in (c.get("/v1/me"),                                          # domain HTTPException(dict) -> 401
                  c.get("/v1/no-such-route"),                               # starlette 404
                  c.delete("/healthz"),                                     # 405
                  c.post("/v1/auth/login", json={"email": 1})):             # 422 validation
            body = r.json()
            self.assertEqual(sorted(body), ["code", "message"], (r.status_code, body))
            self.assertTrue(body["code"] and body["message"])
        self.assertEqual(c.get("/v1/me").json()["code"], "invalid_token")
        self.assertEqual(c.get("/v1/me").headers.get("www-authenticate"), "Bearer")
        self.assertEqual(c.get("/v1/no-such-route").json()["code"], "not_found")
        self.assertEqual(c.post("/v1/auth/login", json={"email": 1}).status_code, 422)

    def test_validation_error_does_not_echo_input(self):
        from fastapi.testclient import TestClient
        secret = "do-not-echo-" + "x" * 8
        r = TestClient(self.app).post("/v1/auth/login", json={"email": secret, "password": {"a": secret}})
        self.assertEqual(r.status_code, 422)
        self.assertNotIn(secret, r.text)

    def test_unhandled_exception_is_a_generic_500_body(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from app.api import errors
        app = FastAPI()
        errors.install(app)

        @app.get("/boom")
        def boom():
            raise RuntimeError("SELECT secret FROM t WHERE x = 'sk-leak'")

        with self.assertLogs("app.api.errors", "ERROR"):
            r = TestClient(app, raise_server_exceptions=False).get("/boom")
        self.assertEqual((r.status_code, r.json()), (500, {"code": "internal_error", "message": "internal error"}))

    def test_create_app_runs_the_api_wiring_and_lifespan_opens_the_pool(self):
        from unittest import mock
        from fastapi.testclient import TestClient
        from app.main import create_app
        with mock.patch("app.api.wiring.wire_api") as wire, \
                mock.patch("app.core.db.open_pool") as op, mock.patch("app.core.db.close_pool") as cp, \
                mock.patch.dict("os.environ", {"DATABASE_URL": "postgresql:///x"}):
            with TestClient(create_app()):
                op.assert_called_once_with("postgresql:///x")
            cp.assert_called_once()
        wire.assert_called_once()

    def test_healthz_without_database(self):
        from fastapi.testclient import TestClient
        self.assertEqual(TestClient(self.app).get("/healthz").json(), {"status": "ok"})


@unittest.skipUnless(HAVE, "fastapi/httpx/pyyaml missing")
class ProcessWiringTest(unittest.TestCase):
    def setUp(self):
        from app.core.events import EventBus
        self.bus = EventBus()

    def names(self):
        return {n for n, hs in self.bus._handlers.items() if hs}

    def calls(self, fn, mods):
        """Which subscribe() hooks fn(bus) invokes (patched out: the real ones latch on the first bus)."""
        import importlib
        from unittest import mock
        seen = []
        with mock.patch("app.domains.ingestion.adapters.register_all", lambda *a, **k: seen.append("adapters")):
            patches = []
            for m in mods:
                mod = importlib.import_module(f"app.domains.{m}.wiring")
                p = mock.patch.object(mod, "subscribe", lambda *a, _m=m, **k: seen.append(_m))
                p.start()
                patches.append(p)
            try:
                fn(self.bus)
            finally:
                for p in patches:
                    p.stop()
        return seen

    ALL = ("workspace", "source", "advisor", "profile", "notification")

    def test_api_wiring_subscribes_everything_the_api_process_needs(self):
        from app.api import wiring
        self.assertEqual(sorted(self.calls(wiring.wire_api, self.ALL)), sorted(self.ALL))

    def test_worker_wiring_subscribes_ingest_reactions_not_identity_ones(self):
        from app.api import wiring
        seen = self.calls(wiring.wire_worker, self.ALL)
        self.assertEqual(sorted(seen), sorted(["adapters", "source", "advisor", "profile", "notification"]))
        self.assertNotIn("workspace", seen)  # identity.user.created is an API-process event

    def test_audit_recorder_and_enqueuer_are_the_public_api_functions(self):
        from app.api import wiring
        from app.domains.audit import api as audit
        from app.domains.identity import router as identity
        from app.domains.ingestion import api as ingestion
        from app.domains.source import wiring as source
        from app.domains.workspace import wiring as workspace
        wiring.wire_api(self.bus)
        self.assertIs(identity._audit, audit.record)
        self.assertIs(workspace._audit, audit.record)
        self.assertIs(source._enqueue, ingestion.enqueue)

    def test_simulation_and_report_seams(self):
        from app.domains.advisor import api as advisor
        from app.domains.quota import api as quota
        from app.domains.simulation import wiring as sim
        from app.domains.usage import api as usage
        self.assertIs(sim._advisor_proposer(), advisor.submit_proposal)
        self.assertIs(getattr(usage, "prices"), usage.prices)
        self.assertTrue(callable(quota.list_budgets))
        import inspect
        from app.domains.report import wiring as report
        self.assertIn("quota.list_budgets", inspect.getsource(report.get_service))

    def test_worker_wiring_registers_every_format_adapter(self):
        from app.api import wiring
        from app.domains.ingestion import registry
        before = list(registry.adapters())
        self.addCleanup(lambda: registry._adapters.__setitem__(slice(None), before))
        registry._adapters[:] = []
        wiring.wire_worker(self.bus)
        self.assertEqual({a.kind for a in registry.adapters()},
                         {"claude_code", "ga_l0", "anthropic_export", "openai_export"})

    def test_notification_subscribe_is_idempotent_per_bus(self):
        from app.domains.notification import wiring as notification
        notification.subscribe(self.bus)
        notification.subscribe(self.bus)
        self.assertEqual(len(self.bus._handlers["ingestion.job.finished"]), 1)

    def test_worker_main_calls_wire_worker(self):
        src = (ROOT / "backend/app/worker/__main__.py").read_text()
        self.assertRegex(src, r"wire_worker\(\)")
        self.assertLess(src.index("open_pool(s.database_url)"), src.index("wire_worker()"))
        self.assertTrue((ROOT / "backend/app/worker/README.md").read_text().count("아웃박스") >= 1)


class ListBudgetsTest(unittest.TestCase):
    def test_list_budgets_returns_active_budgets_of_the_workspace_only(self):
        from app.domains.quota import api as quota
        from app.domains.quota import wiring
        from app.domains.quota.service import MemoryStore, QuotaService
        svc = QuotaService(MemoryStore(), lambda *a, **k: {})
        wiring.set_service(svc)
        self.addCleanup(wiring.set_service, None)
        a = svc.create("w1", "u", "workspace", "month", "list", 5_000_000)
        b = svc.create("w1", "u", "workspace", "day", "cli", 100)
        svc.create("w2", "u", "workspace", "month", "list", 9)
        svc.archive("w1", b.id)
        got = quota.list_budgets("w1")
        self.assertEqual([x["id"] for x in got], [a.id])
        self.assertEqual(got[0]["limit_microusd"], 5_000_000)
        self.assertEqual(quota.list_budgets("nobody"), [])


if __name__ == "__main__":
    unittest.main()

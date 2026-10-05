import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest import mock

try:
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
except ImportError:
    FastAPI = None

from app.domains.usage.service import CallIn, MemoryStore, UsageService

WS = "00000000-0000-4000-8000-000000000001"
NOW = datetime.now(timezone.utc)


@unittest.skipIf(FastAPI is None, "fastapi not installed")
class RouteTest(unittest.TestCase):
    def setUp(self):
        from app.domains.usage import router as r, wiring
        self.svc = UsageService(MemoryStore())
        wiring.set_service(self.svc)
        self.addCleanup(wiring.set_service, None)
        self.role = {"role": "viewer"}

        def fake_require(ws, uid, min_role="viewer"):
            order = ("viewer", "developer", "admin")
            if ws != WS:
                raise __import__("fastapi").HTTPException(404, detail={"code": "not_found", "message": "x"})
            if order.index(self.role["role"]) < order.index(min_role):
                raise __import__("fastapi").HTTPException(403, detail={"code": "forbidden", "message": "x"})
        p = mock.patch.object(r, "require_member", fake_require)
        p.start()
        self.addCleanup(p.stop)
        app = FastAPI()
        app.include_router(r.router)
        app.dependency_overrides[r.current_user] = lambda: SimpleNamespace(id="u1")
        self.c = TestClient(app)
        self.svc.load_calls(WS, None, "s", "j", [CallIn("claude-sonnet-5-5", "anthropic", "claude_code",
                                                        NOW - timedelta(hours=1), "k", input_tokens=10,
                                                        output_tokens=5, task="r")])

    def test_reads_and_boundaries(self):
        self.assertEqual(len(self.c.get("/v1/models").json()), 2)
        for path in ("summary", "series/tokens", "series/call-size", "calls", "sessions", "tasks",
                     "compare?dims=model"):
            self.assertEqual(self.c.get(f"/v1/workspaces/{WS}/usage/{path}").status_code, 200, path)
        self.assertEqual(self.c.get("/v1/workspaces/00000000-0000-4000-8000-0000000000ee/usage/summary").status_code, 404)
        self.assertEqual(self.c.get(f"/v1/workspaces/{WS}/usage/compare?dims=bad").status_code, 422)

    def test_patch_needs_developer(self):
        tid = self.c.get(f"/v1/workspaces/{WS}/usage/tasks").json()["items"][0]["id"]
        url = f"/v1/workspaces/{WS}/usage/tasks/{tid}"
        self.assertEqual(self.c.patch(url, json={"outcome": "correct"}).status_code, 403)
        self.role["role"] = "developer"
        r = self.c.patch(url, json={"outcome": "correct"})
        self.assertEqual((r.status_code, r.json()["outcome"]), (200, "correct"))

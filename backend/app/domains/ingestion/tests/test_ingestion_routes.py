import unittest
from types import SimpleNamespace
from unittest import mock

try:
    from fastapi import FastAPI, HTTPException
    from fastapi.testclient import TestClient
except ImportError:
    FastAPI = None

from app.domains.ingestion import registry

from .helpers import WS, make
from .test_ingestion import GOOD


@unittest.skipIf(FastAPI is None, "fastapi not installed")
class RouteTest(unittest.TestCase):
    def setUp(self):
        from app.domains.ingestion import router as r, wiring

        self.svc, _, _ = make({"u1": GOOD})
        wiring.set_service(self.svc)
        self.addCleanup(wiring.set_service, None)
        self.addCleanup(registry.unregister, "claude_code")

        def fake_require(ws, uid, min_role="viewer"):
            if ws != WS:
                raise HTTPException(404, detail={"code": "not_found", "message": "x"})
        p = mock.patch.object(r, "require_member", fake_require)
        p.start()
        self.addCleanup(p.stop)
        app = FastAPI()
        app.include_router(r.router)
        app.dependency_overrides[r.current_user] = lambda: SimpleNamespace(id="u")
        self.c = TestClient(app)
        self.jid = self.svc.enqueue("u1")
        self.svc.run_one("w")

    def test_list_and_get(self):
        self.assertEqual(self.c.get(f"/v1/workspaces/{WS}/ingest-jobs").json()[0]["id"], self.jid)
        j = self.c.get(f"/v1/workspaces/{WS}/ingest-jobs/{self.jid}").json()
        self.assertEqual((j["state"], j["inserted"], j["rejected"]), ("done", 2, 2))
        self.assertEqual(self.c.get(f"/v1/workspaces/{WS}/ingest-jobs/nope").status_code, 404)
        self.assertEqual(self.c.get("/v1/workspaces/00000000-0000-4000-8000-0000000000ee/ingest-jobs").status_code, 404)

    def test_sse_resume_with_last_event_id_header(self):
        url = f"/v1/workspaces/{WS}/ingest-jobs/{self.jid}/events"
        r = self.c.get(url)
        self.assertEqual(r.headers["content-type"].split(";")[0], "text/event-stream")
        self.assertEqual(r.text.count("id: "), 6)
        r = self.c.get(url, headers={"Last-Event-ID": "4"})
        self.assertEqual([l for l in r.text.splitlines() if l.startswith("id: ")], ["id: 5", "id: 6"])
        self.assertEqual(self.c.get(f"/v1/workspaces/{WS}/ingest-jobs/nope/events").status_code, 404)

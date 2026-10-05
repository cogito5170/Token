"""report HTTP routes: a malformed report id answers 404 {code,message}, never 500 (CMD-GC19 open item).
Skipped without fastapi/httpx."""
import unittest
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest import mock

try:
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    HAVE = True
except ImportError:
    HAVE = False

from app.domains.report.service import MemoryStore, ReportService

WS = "00000000-0000-4000-8000-000000000001"
NOW = datetime(2026, 10, 10, 12, 0, tzinfo=timezone.utc)


class UuidStrictStore(MemoryStore):
    """PostgreSQL rejects a non-uuid text in `id = %s` with a DataError; model that, so an unvalidated id shows up as 500."""

    def get(self, ws, rid):
        uuid.UUID(rid)
        return super().get(ws, rid)


def summary(ws, frm, to, project=None):
    return {"tiles": {"total_tokens": {"value": 5, "unit": "tokens", "provenance": "MEASURED"}}}


@unittest.skipUnless(HAVE, "fastapi/httpx missing")
class ReportRouteTest(unittest.TestCase):
    def setUp(self):
        from app.api import errors
        from app.domains.identity.api import current_user
        from app.domains.report import router as r
        from app.domains.report import wiring
        self.svc = ReportService(UuidStrictStore(), summary, lambda *a: [], lambda ws: [], lambda *a: {},
                                 audit=lambda *a, **k: None, publish=lambda *a: None, now=lambda: NOW)
        wiring.set_service(self.svc)
        self.addCleanup(wiring.set_service, None)
        p = mock.patch.object(r, "require_member", lambda ws, uid, role="viewer": None)
        p.start()
        self.addCleanup(p.stop)
        app = FastAPI()
        errors.install(app)
        app.include_router(r.router)
        app.dependency_overrides[current_user] = lambda: SimpleNamespace(id="u1")
        self.c = TestClient(app)

    def test_malformed_id_is_404_with_code_and_message(self):
        for bad in ("abc", "1", "not-a-uuid", "00000000-0000-0000-0000-00000000000g"):
            res = self.c.get(f"/v1/workspaces/{WS}/reports/{bad}/export", params={"format": "csv"})
            self.assertEqual(res.status_code, 404, bad)
            self.assertEqual(res.json(), {"code": "not_found", "message": "report not found"})

    def test_unknown_but_well_formed_id_is_404_and_real_report_exports(self):
        res = self.c.get(f"/v1/workspaces/{WS}/reports/{uuid.uuid4()}/export", params={"format": "json"})
        self.assertEqual(res.status_code, 404)
        self.assertEqual(res.json()["code"], "not_found")
        rid = self.c.post(f"/v1/workspaces/{WS}/reports", json={"from": "2026-10-01", "to": "2026-10-31"}).json()["id"]
        ok = self.c.get(f"/v1/workspaces/{WS}/reports/{rid}/export", params={"format": "csv"})
        self.assertEqual(ok.status_code, 200)
        self.assertIn("text/csv", ok.headers["content-type"])


if __name__ == "__main__":
    unittest.main()

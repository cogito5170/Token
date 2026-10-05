import hashlib
import io
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone

from app.core.events import EventBus
from app.domains.source.service import FileObjectStore, MemoryStore, SourceError, SourceService

WS = "00000000-0000-4000-8000-0000000000a1"
U1 = "00000000-0000-4000-8000-000000000001"


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.bus, self.seen = EventBus(), []
        self.bus.subscribe("source.upload.stored", lambda n, p: self.seen.append(p))
        self.store = MemoryStore()
        self.now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        self.svc = SourceService(self.store, FileObjectStore(self.tmp.name), 10, publish=self.bus.publish,
                                 enqueue=lambda uid: "job-" + uid, now=lambda: self.now)
        self.src = self.svc.create_source(WS, "upload", "my logs")


class UploadTest(Base):
    def test_stores_sha256_size_path_and_purge_after(self):
        data = b"hello"
        u = self.svc.create_upload(WS, U1, self.src.id, "../x/log.jsonl", io.BytesIO(data), "claude_code")
        self.assertEqual(u.sha256, hashlib.sha256(data).hexdigest())
        self.assertEqual(u.size_bytes, 5)
        self.assertEqual(u.filename, "log.jsonl")
        self.assertEqual(u.storage_path, f"{WS}/{u.id}")
        self.assertEqual(u.purge_after, self.now + timedelta(days=7))
        self.assertEqual(u.job_id, "job-" + u.id)
        with self.svc.open_upload(u.id) as f:
            self.assertEqual(f.read(), data)

    def test_over_limit_is_413_and_leaves_nothing(self):
        with self.assertRaises(SourceError) as c:
            self.svc.create_upload(WS, U1, self.src.id, "big", io.BytesIO(b"x" * 11))
        self.assertEqual(c.exception.status, 413)
        self.assertEqual(self.store.up, {})
        self.assertEqual(self.seen, [])
        self.assertEqual([f for _, _, fs in os.walk(self.tmp.name) for f in fs], [])

    def test_exactly_at_limit_is_ok(self):
        self.assertEqual(self.svc.create_upload(WS, U1, self.src.id, "f", io.BytesIO(b"x" * 10)).size_bytes, 10)

    def test_declared_size_over_limit_is_413_without_reading(self):
        with self.assertRaises(SourceError) as c:
            self.svc.create_upload(WS, U1, self.src.id, "f", io.BytesIO(b""), declared_size=11)
        self.assertEqual(c.exception.status, 413)

    def test_event_carries_ids_only(self):
        u = self.svc.create_upload(WS, U1, self.src.id, "secret-name.jsonl", io.BytesIO(b"abc"))
        self.assertEqual(self.seen, [{"workspace_id": WS, "source_id": self.src.id, "upload_id": u.id}])

    def test_source_of_another_workspace_is_404(self):
        other = "00000000-0000-4000-8000-0000000000b2"
        with self.assertRaises(SourceError) as c:
            self.svc.create_upload(other, U1, self.src.id, "f", io.BytesIO(b"a"))
        self.assertEqual(c.exception.status, 404)
        self.assertEqual(self.svc.sources(other), [])

    def test_bad_declared_format_and_source_kind(self):
        with self.assertRaises(SourceError) as c:
            self.svc.create_upload(WS, U1, self.src.id, "f", io.BytesIO(b"a"), "nope")
        self.assertEqual(c.exception.status, 422)
        with self.assertRaises(SourceError):
            self.svc.create_source(WS, "otel", "x")
        with self.assertRaises(SourceError):
            self.svc.create_source(WS, "upload", "  ")

    def test_purged_or_unknown_upload_is_404(self):
        u = self.svc.create_upload(WS, U1, self.src.id, "f", io.BytesIO(b"a"))
        u.purged_at = self.now
        for uid in (u.id, "nope", "00000000-0000-4000-8000-0000000000ff"):
            with self.assertRaises(SourceError):
                self.svc.open_upload(uid)

    def test_job_finished_restarts_purge_clock(self):
        u = self.svc.create_upload(WS, U1, self.src.id, "f", io.BytesIO(b"a"))
        self.now += timedelta(days=3)
        self.svc.on_job_finished("ingestion.job.finished", {"upload_id": u.id})
        self.assertEqual(self.store.up[u.id].purge_after, self.now + timedelta(days=7))
        self.svc.on_job_finished("ingestion.job.finished", {})  # no upload id: ignored


class ObjectStoreTest(unittest.TestCase):
    def test_key_escape_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError):
                FileObjectStore(d).put("../evil", [b"x"])


try:
    import fastapi  # noqa: F401
    import multipart  # noqa: F401
    HAVE_API = True
except ImportError:
    HAVE_API = False


@unittest.skipUnless(HAVE_API, "fastapi/python-multipart not installed")
class HttpTest(Base):
    def setUp(self):
        super().setUp()
        from types import SimpleNamespace

        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from app.domains.source import router as r
        from app.domains.source import wiring

        wiring._service = self.svc
        self.addCleanup(setattr, wiring, "_service", None)
        self.role = "developer"
        app = FastAPI()
        app.dependency_overrides[r.current_user] = lambda: SimpleNamespace(id=U1)

        def fake_member(ws, uid, min_role="viewer"):
            from fastapi import HTTPException
            if ws != WS:
                raise HTTPException(404)
            if min_role == "developer" and self.role == "viewer":
                raise HTTPException(403)
        self._orig = r.require_member
        r.require_member = fake_member
        self.addCleanup(setattr, r, "require_member", self._orig)
        app.include_router(r.router)
        self.c = TestClient(app)

    def test_upload_413_and_201(self):
        url = f"/v1/workspaces/{WS}/uploads"
        big = self.c.post(url, data={"source_id": self.src.id}, files={"file": ("a.jsonl", b"x" * 11)})
        self.assertEqual(big.status_code, 413)
        self.assertEqual(big.json()["detail"]["code"], "payload_too_large")
        ok = self.c.post(url, data={"source_id": self.src.id}, files={"file": ("a.jsonl", b"abc")})
        self.assertEqual(ok.status_code, 201)
        self.assertEqual(ok.json()["sha256"], hashlib.sha256(b"abc").hexdigest())

    def test_roles_and_boundary(self):
        self.role = "viewer"
        self.assertEqual(self.c.post(f"/v1/workspaces/{WS}/sources", json={"kind": "upload", "name": "n"}).status_code, 403)
        self.assertEqual(self.c.get(f"/v1/workspaces/{WS}/sources").status_code, 200)
        self.assertEqual(self.c.get("/v1/workspaces/00000000-0000-4000-8000-0000000000b2/sources").status_code, 404)


if __name__ == "__main__":
    unittest.main()

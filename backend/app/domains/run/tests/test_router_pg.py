"""run monitor routes over HTTP against fixtures/monitor and a real PostgreSQL 16 (ga_dirs). Skipped without
GC_SCHEMA_TEST_DSN, psql, psycopg, fastapi, httpx or uvicorn."""
import hashlib
import json
import os
import shutil
import socket
import subprocess
import tempfile
import threading
import time
import unittest
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from app.domains.run import gadir, replay

DSN = os.environ.get("GC_SCHEMA_TEST_DSN")
REPO = Path(__file__).resolve().parents[5]
try:
    import httpx
    import psycopg  # noqa: F401
    import uvicorn
    from fastapi import FastAPI, HTTPException
    from fastapi.testclient import TestClient
    HAVE = True
except ImportError:
    HAVE = False
RANK = {"viewer": 0, "developer": 1, "admin": 2}


def tree_state(root):
    out = {}
    for d, dirs, files in os.walk(root):
        for n in dirs + files:
            p = os.path.join(d, n)
            out[p] = (os.stat(p).st_mtime_ns, hashlib.sha256(Path(p).read_bytes()).hexdigest() if os.path.isfile(p) else "")
    return out


def parse_sse(text):
    frames = []
    for block in text.split("\n\n"):
        f = dict(line.split(": ", 1) for line in block.split("\n") if ": " in line and not line.startswith(":"))
        if f:
            frames.append(f)
    return frames


@unittest.skipUnless(DSN and shutil.which("psql") and HAVE, "GC_SCHEMA_TEST_DSN, psql, psycopg, fastapi or uvicorn missing")
class MonitorHttpTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from app.core import db
        os.environ["GC_MONITOR_POLL_MS"] = "50"
        cls.name = "gc_run_" + uuid.uuid4().hex[:8]
        run = lambda dsn, *a: subprocess.run(["psql", dsn, "-v", "ON_ERROR_STOP=1", "-qAt", *a],  # noqa: E731
                                              capture_output=True, text=True, timeout=120)
        assert run(DSN, "-c", f"CREATE DATABASE {cls.name}").returncode == 0
        cls.dsn = DSN.rsplit("/", 1)[0] + "/" + cls.name
        assert run(cls.dsn, "-f", str(REPO / "docs" / "schema.sql")).returncode == 0
        cls.pool = db.open_pool(cls.dsn)
        with cls.pool.connection() as c:
            cls.user = str(c.execute("INSERT INTO users (email, display_name, password_hash) VALUES "
                                     "('r@example.com','r','x') RETURNING id").fetchone()[0])
            mk = lambda n: str(c.execute("INSERT INTO workspaces (name, slug, created_by) VALUES (%s,%s,%s) "  # noqa: E731
                                         "RETURNING id", (n, n, cls.user)).fetchone()[0])
            cls.ws, cls.other_ws = mk("w1"), mk("w2")
        cls.td = tempfile.TemporaryDirectory()
        cls.ga = os.path.join(cls.td.name, ".ga")
        os.makedirs(cls.ga)
        script = json.loads((REPO / "fixtures" / "monitor" / "script.json").read_text(encoding="utf-8"))
        replay.replay(script, cls.ga, gadir.GaDirReader)  # builds the fixture tree; the app reads it afterwards

    @classmethod
    def tearDownClass(cls):
        from app.core import db
        from app.domains.run import router
        router.stop_monitors()
        cls.td.cleanup()
        db.close_pool()
        subprocess.run(["psql", DSN, "-qAt", "-c", f"DROP DATABASE {cls.name} WITH (FORCE)"], capture_output=True)

    def setUp(self):
        from app.api import errors
        from app.domains.identity.api import current_user
        from app.domains.run import router
        router.set_sources(None)
        self.addCleanup(router.set_sources, None)
        self.role, self.calls, self.audit = "admin", [], []
        self.members = {self.ws}  # workspaces the caller belongs to

        def require_member(ws, uid, min_role="viewer"):
            self.calls.append((ws, min_role))
            if ws not in self.members:
                raise HTTPException(404, detail={"code": "not_found", "message": "workspace not found"})
            if RANK[self.role] < RANK[min_role]:
                raise HTTPException(403, detail={"code": "forbidden", "message": "requires role " + min_role})

        for name, val in (("require_member", require_member),
                          ("_record", lambda *a, **k: self.audit.append((a, k)))):
            p = mock.patch.object(router, name, val)
            p.start()
            self.addCleanup(p.stop)
        self.app = FastAPI()
        errors.install(self.app)
        self.app.include_router(router.router)
        self.app.dependency_overrides[current_user] = lambda: SimpleNamespace(id=self.user)
        self.c = TestClient(self.app)
        self.base = f"/v1/workspaces/{self.ws}/monitor/sources"

    def register(self, path=None, label="fixture"):
        return self.c.post(self.base, json={"label": label, "path": path or self.ga})

    def source_id(self):
        r = self.register()
        if r.status_code == 409:
            return next(s["id"] for s in self.c.get(self.base).json() if s["path"] == os.path.realpath(self.ga))
        return r.json()["id"]

    def test_register_list_and_validation(self):
        r = self.register()
        self.assertIn(r.status_code, (201, 409))
        sid = self.source_id()
        listed = self.c.get(self.base).json()
        self.assertEqual([s["id"] for s in listed if s["id"] == sid], [sid])
        got = next(s for s in listed if s["id"] == sid)
        self.assertEqual((got["label"], got["path"], got["reachable"]), ("fixture", os.path.realpath(self.ga), True))
        self.assertEqual(self.c.get(f"/v1/workspaces/{self.other_ws}/monitor/sources").status_code, 404)
        self.assertEqual(self.register().status_code, 409)  # same directory twice
        self.assertEqual(self.register().json()["code"], "conflict")
        file_path = os.path.join(self.td.name, "afile")
        Path(file_path).write_text("x")
        for body in ({"label": "x", "path": "relative/dir"}, {"label": "x", "path": file_path},
                     {"label": "x", "path": os.path.join(self.td.name, "missing")}, {"label": " ", "path": self.ga},
                     {"label": "x" * 201, "path": self.ga}, {"path": self.ga}, {"label": "x", "path": 5}):
            res = self.c.post(self.base, json=body)
            self.assertEqual(res.status_code, 422, body)
            self.assertEqual(sorted(res.json()), ["code", "message"])

    def test_register_is_admin_only_and_audited_without_the_path(self):
        self.audit.clear()
        other = os.path.join(self.td.name, "other_ga")
        os.makedirs(other, exist_ok=True)
        self.role = "developer"
        self.assertEqual(self.register(other).status_code, 403)
        self.assertEqual(self.audit, [])
        self.role = "admin"
        r = self.register(other, "second")
        self.assertEqual(r.status_code, 201)
        (args, kw), = self.audit
        self.assertEqual(args[0], "monitor.source_registered")
        self.assertEqual(args[1], self.user)
        self.assertNotIn(other, json.dumps([args, kw]))
        self.assertEqual(kw["target_id"], r.json()["id"])
        self.role = "viewer"
        self.assertEqual(self.c.get(self.base).status_code, 200)  # reads need membership only
        self.assertIn((self.ws, "admin"), self.calls)

    def test_snapshot_matches_the_reader_fold_of_the_fixture(self):
        sid = self.source_id()
        snap = self.c.get(f"{self.base}/{sid}/snapshot")
        self.assertEqual(snap.status_code, 200)
        body = snap.json()
        self.assertEqual(sorted(body), ["edges", "figures", "meters", "mood", "observed_at", "round", "tiles"])
        self.assertGreaterEqual(len(body["figures"]), 1)
        self.assertEqual(sorted(body["mood"]), ["all_done", "collaboration", "pace", "stall", "tension"])
        ref = gadir.GaDirReader(self.ga)
        ref.poll()
        want = ref.full_snapshot()
        strip = lambda s: {k: [{x: y for x, y in f.items() if x not in ("elapsed_ms", "since")} for f in v] if k == "figures" else v  # noqa: E731
                           for k, v in s.items() if k not in ("observed_at", "mood")}
        self.assertEqual(strip(body), strip(want))
        self.assertEqual(body["round"], 3)  # the fixture's last pool.json round

    def test_unknown_malformed_or_foreign_source_is_404(self):
        sid = self.source_id()
        for path in ("snapshot", "events", "recordings", f"recordings/{uuid.uuid4()}"):
            for bad in ("abc", str(uuid.uuid4())):
                r = self.c.get(f"{self.base}/{bad}/{path}")
                self.assertEqual((r.status_code, r.json()["code"]), (404, "not_found"), (bad, path))
            self.assertEqual(self.c.get(f"/v1/workspaces/{self.other_ws}/monitor/sources/{sid}/{path}").status_code, 404)

    # A bad Last-Event-ID answers 422 on /events, so a route that wrongly lets the caller in fails the test instead of
    # opening an endless stream that TestClient would wait on. Other routes ignore the header.
    NO_STREAM = {"Last-Event-ID": "x"}

    def routes_of(self, ws, sid, rec):
        base = f"/v1/workspaces/{ws}/monitor/sources/{sid}"
        return [f"{base}/snapshot", f"{base}/events", f"{base}/recordings", f"{base}/recordings/{rec}"]

    def test_a_source_is_reachable_only_through_its_own_workspace(self):
        sid = self.source_id()
        rec = self.c.get(f"{self.base}/{sid}/recordings").json()[0]["id"]
        self.members = {self.ws, self.other_ws}  # one user, member of both workspaces
        for url in self.routes_of(self.other_ws, sid, rec):
            r = self.c.get(url, headers=self.NO_STREAM)
            self.assertEqual(r.status_code, 404, url)
            self.assertEqual(r.json()["code"], "not_found")
        self.assertEqual(self.c.get(f"/v1/workspaces/{self.other_ws}/monitor/sources").json(), [])
        self.assertEqual(self.c.get(self.routes_of(self.ws, sid, rec)[0]).status_code, 200)

    def test_non_member_gets_404_on_every_route_of_a_real_source(self):
        sid = self.source_id()
        rec = self.c.get(f"{self.base}/{sid}/recordings").json()[0]["id"]
        urls = self.routes_of(self.ws, sid, rec)
        self.assertEqual([self.c.get(u, timeout=5).status_code for u in urls[:1] + urls[2:]], [200, 200, 200])
        self.members = set()
        for url in urls + [self.base]:
            r = self.c.get(url, headers=self.NO_STREAM)
            self.assertEqual(r.status_code, 404, url)
            self.assertEqual(r.json()["code"], "not_found")

    def test_recordings_list_and_ndjson_agree_with_the_event_log(self):
        sid = self.source_id()
        recs = self.c.get(f"{self.base}/{sid}/recordings").json()
        self.assertEqual(len(recs), 1)
        rec = recs[0]
        self.assertEqual((rec["ended_at"], rec["reader_version"]), (None, gadir.READER_VERSION))
        self.assertGreater(rec["events"], 5)
        nd = self.c.get(f"{self.base}/{sid}/recordings/{rec['id']}")
        self.assertEqual(nd.headers["content-type"].split(";")[0], "application/x-ndjson")
        events = [json.loads(x) for x in nd.text.splitlines()]
        self.assertEqual([e["seq"] for e in events], list(range(1, len(events) + 1)))
        self.assertGreaterEqual(len(events), rec["events"])
        for e in events:
            for k in ("seq", "observed_at", "kind", "data", "provenance"):
                self.assertIn(k, e)
            self.assertRegex(e["kind"], r"^(l0|file|derived):[a-z_.]+$")
        self.assertEqual(self.c.get(f"{self.base}/{sid}/recordings/{uuid.uuid4()}").status_code, 404)

    def test_every_route_is_read_only_and_never_writes_inside_the_ga_dir(self):
        sid = self.source_id()
        before = tree_state(self.ga)
        rec = self.c.get(f"{self.base}/{sid}/recordings").json()[0]["id"]
        for p in ("snapshot", "recordings", f"recordings/{rec}"):
            self.assertEqual(self.c.get(f"{self.base}/{sid}/{p}").status_code, 200)
        for m in ("post", "put", "patch", "delete"):
            for p in ("snapshot", "events", "recordings"):
                self.assertEqual(getattr(self.c, m)(f"{self.base}/{sid}/{p}").status_code, 405, (m, p))
        time.sleep(0.3)  # several poll intervals
        self.assertEqual(tree_state(self.ga), before)
        self.assertEqual(self.c.get(f"/v1/workspaces/{self.ws}/runs").status_code, 404)  # x-later: not served

    def test_events_last_event_id_must_be_a_non_negative_integer(self):
        sid = self.source_id()
        for bad in ("abc", "-1", "1.5", ""):
            r = self.c.get(f"{self.base}/{sid}/events", headers={"Last-Event-ID": bad})
            self.assertEqual((r.status_code, r.json()["code"]), (422, "invalid_request"), bad)

    # -- SSE over a real socket: TestClient buffers a response, a stream needs a server -------------------------
    def serve(self):
        s = socket.socket()
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
        s.close()
        srv = uvicorn.Server(uvicorn.Config(self.app, host="127.0.0.1", port=port, log_level="error"))
        t = threading.Thread(target=srv.run, daemon=True)
        t.start()
        for _ in range(100):
            if srv.started:
                break
            time.sleep(0.05)
        self.addCleanup(lambda: (setattr(srv, "should_exit", True), t.join(5)))
        return f"http://127.0.0.1:{port}"

    def read_sse(self, url, headers, n):
        """First n frames with an id (comments skipped), then the connection is dropped."""
        frames, buf = [], ""
        with httpx.Client(timeout=httpx.Timeout(1.5)) as h, h.stream("GET", url, headers=headers) as r:
            self.assertEqual(r.status_code, 200)
            self.assertTrue(r.headers["content-type"].startswith("text/event-stream"))
            try:
                for chunk in r.iter_text():
                    buf += chunk
                    parts = buf.split("\n\n")
                    buf = parts.pop()
                    frames += [f for f in parse_sse("\n\n".join(parts)) if "id" in f]
                    if len(frames) >= n:
                        break
            except httpx.ReadTimeout:
                pass
        return frames

    def test_sse_resumes_from_last_event_id(self):
        sid = self.source_id()
        total = self.c.get(f"{self.base}/{sid}/recordings").json()[0]["events"]
        want = [json.loads(x) for x in self.c.get(
            f"{self.base}/{sid}/recordings/{self.c.get(f'{self.base}/{sid}/recordings').json()[0]['id']}"
        ).text.splitlines()]
        root = self.serve()
        url = f"{root}/v1/workspaces/{self.ws}/monitor/sources/{sid}/events"
        full = self.read_sse(url, {}, total)
        self.assertEqual([int(f["id"]) for f in full][:total], list(range(1, total + 1)))
        for f in full:
            e = want[int(f["id"]) - 1]
            self.assertEqual(f["event"], e["kind"])
            self.assertEqual(json.loads(f["data"]), e)
        k = total // 2
        rest = self.read_sse(url, {"Last-Event-ID": str(k)}, total - k)
        self.assertEqual([int(f["id"]) for f in rest][:total - k], list(range(k + 1, total + 1)))
        self.assertTrue(all(int(f["id"]) > k for f in rest))
        self.assertEqual(self.read_sse(url, {"Last-Event-ID": str(len(want))}, 1), [])  # nothing newer yet

    def test_sse_frames_generator_heartbeat_and_stop(self):
        from app.domains.run import router
        mon = router._monitor(next(s for s in router.get_sources().list(self.ws)
                                   if s["path"] == os.path.realpath(self.ga)) if router.get_sources().list(self.ws)
                              else {"id": self.source_id(), "path": os.path.realpath(self.ga)})
        n = {"i": 0}

        def done():
            n["i"] += 1
            return n["i"] > 6
        out = b"".join(router.sse_frames(mon, mon.events_after(0)[-1]["seq"], heartbeat_s=0.05, done=done))
        self.assertIn(b": heartbeat\n\n", out)
        self.assertNotIn(b"id: ", out)


if __name__ == "__main__":
    unittest.main()

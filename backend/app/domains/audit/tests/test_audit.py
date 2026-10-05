import os
import shutil
import subprocess
import unittest
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.domains.audit.service import AuditError, AuditService, MemoryStore

WS = "00000000-0000-4000-8000-0000000000a1"
U1 = "00000000-0000-4000-8000-000000000001"
SCHEMA = Path(__file__).resolve().parents[5] / "docs" / "schema.sql"
DSN = os.environ.get("GC_SCHEMA_TEST_DSN")
# fake key-shaped values, assembled so infra/secret_scan.py stays clean
FAKE_SK = "s" + "k-" + "x" * 24
FAKE_GH = "gh" + "p_" + "A" * 36
FAKE_PEM = "-----BEGIN " + "PRIVATE KEY-----"


def make():
    store = MemoryStore()
    return AuditService(store), store


class RecordTest(unittest.TestCase):
    def test_record_derives_workspace_and_target(self):
        svc, store = make()
        r = svc.record("workspace.member_added", U1, {"workspace_id": WS, "user_id": U1, "role": "viewer"})
        self.assertEqual((r.workspace_id, r.actor_user_id, r.actor_kind), (WS, U1, "user"))
        self.assertEqual((r.target_kind, r.target_id), ("workspace", WS))
        self.assertEqual(len(store.rows), 1)

    def test_system_actor_and_explicit_target(self):
        svc, _ = make()
        r = svc.record("budget.update", None, {}, workspace_id=WS, target_kind="budget", target_id="b1")
        self.assertEqual((r.actor_kind, r.actor_user_id, r.target_kind, r.target_id), ("system", None, "budget", "b1"))

    def test_key_shaped_detail_rejected(self):
        svc, store = make()
        for d in ({"note": FAKE_SK}, {"a": {"b": [FAKE_GH]}}, {"pem": FAKE_PEM},
                  {"auth": "Bearer " + "a" * 24}, {"api_key": "anything"}, {"password": "x"}):
            with self.assertRaises(AuditError) as c:
                svc.record("x.y", U1, d, workspace_id=WS)
            self.assertEqual((c.exception.status, c.exception.code), (422, "audit.detail_secret"))
        self.assertEqual(store.rows, [])

    def test_ids_counts_and_flags_are_allowed(self):
        svc, _ = make()
        svc.record("credential.store", U1, {"token_count": 12, "has_password": True, "credential_id": "c1",
                                            "fingerprint": "ab12", "last4": "wxyz"}, workspace_id=WS)

    def test_bad_inputs(self):
        svc, _ = make()
        for kw in ({"action": ""}, {"action": "x" * 200}, {"action": "a.b", "actor_kind": "root"}):
            with self.assertRaises(AuditError):
                svc.record(kw.pop("action"), None, {}, **kw)
        with self.assertRaises(AuditError):
            svc.record("a.b", None, {"blob": "z" * 9000})


class QueryTest(unittest.TestCase):
    def test_non_admin_forbidden(self):
        svc, _ = make()
        for role in ("viewer", "developer"):
            with self.assertRaises(AuditError) as c:
                svc.query(WS, role)
            self.assertEqual(c.exception.status, 403)

    def test_admin_paging_filter_and_isolation(self):
        svc, _ = make()
        for i in range(5):
            svc.record("a.one" if i % 2 else "a.two", U1, {"n": i}, workspace_id=WS)
        svc.record("a.one", U1, {}, workspace_id="00000000-0000-4000-8000-0000000000b2")
        rows, nxt = svc.query(WS, "admin", limit=2)
        self.assertEqual([r.detail["n"] for r in rows], [4, 3])
        rows2, nxt2 = svc.query(WS, "admin", limit=2, cursor=nxt)
        self.assertEqual([r.detail["n"] for r in rows2], [2, 1])
        rows3, nxt3 = svc.query(WS, "admin", limit=2, cursor=nxt2)
        self.assertEqual(([r.detail["n"] for r in rows3], nxt3), ([0], None))
        only, _ = svc.query(WS, "admin", action="a.one")
        self.assertEqual(len(only), 2)
        future = datetime.now(timezone.utc) + timedelta(days=1)
        self.assertEqual(svc.query(WS, "admin", frm=future)[0], [])
        with self.assertRaises(AuditError):
            svc.query(WS, "admin", cursor="nope")

    def test_memory_store_is_append_only(self):
        _, store = make()
        with self.assertRaises(AuditError):
            store.update()
        with self.assertRaises(AuditError):
            store.delete()


@unittest.skipUnless(DSN and shutil.which("psql"), "GC_SCHEMA_TEST_DSN not set or psql missing")
class PgAppendOnlyTest(unittest.TestCase):
    """UPDATE / DELETE on audit_log raise (trigger from docs/schema.sql), and PgStore round-trips."""

    def psql(self, dsn, *args):
        return subprocess.run(["psql", dsn, "-v", "ON_ERROR_STOP=1", "-qAt", *args],
                              capture_output=True, text=True, timeout=120)

    def setUp(self):
        try:
            import psycopg  # noqa: F401
            import psycopg_pool  # noqa: F401
        except ImportError:
            self.skipTest("psycopg not installed")
        self.name = "gc_audit_" + uuid.uuid4().hex[:8]
        self.assertEqual(self.psql(DSN, "-c", f"CREATE DATABASE {self.name}").returncode, 0)
        self.db = DSN.rsplit("/", 1)[0] + "/" + self.name
        r = self.psql(self.db, "-f", str(SCHEMA))
        self.assertEqual(r.returncode, 0, r.stderr)

    def tearDown(self):
        self.psql(DSN, "-c", f"DROP DATABASE IF EXISTS {self.name} WITH (FORCE)")

    def test_update_delete_raise_and_store_roundtrip(self):
        from psycopg_pool import ConnectionPool

        from app.domains.audit.pg_store import PgStore

        with ConnectionPool(self.db, min_size=1, max_size=2, open=True) as pool:
            svc = AuditService(PgStore(pool))
            svc.record("proposal.apply", U1, {"workspace_id": WS, "proposal_id": "p1", "n": 3}, workspace_id=None)
            svc.record("proposal.apply", None, {"proposal_id": "p2"}, workspace_id=WS)
            rows, nxt = svc.query(WS, "admin", action="proposal.apply")
            self.assertEqual([r.target_id for r in rows], ["p2", "p1"])
            self.assertEqual(rows[1].detail, {"workspace_id": WS, "proposal_id": "p1", "n": 3})
            self.assertIsNone(nxt)
            for sql in ("UPDATE audit_log SET action='x'", "DELETE FROM audit_log"):
                with self.assertRaises(Exception) as c, pool.connection() as conn:
                    conn.execute(sql)
                self.assertIn("append-only", str(c.exception))
            self.assertEqual(len(svc.query(WS, "admin")[0]), 2)


class HttpTest(unittest.TestCase):
    """GET /audit-log through FastAPI with the workspace and identity dependencies replaced by fakes."""

    def setUp(self):
        try:
            from fastapi import FastAPI
            from fastapi.testclient import TestClient
        except ImportError:
            self.skipTest("fastapi/httpx not installed")
        import app.domains.workspace.api as wapi
        from app.domains.audit import router as r
        from app.domains.audit import wiring
        from app.domains.workspace.service import MemberRow, WorkspaceError

        self.svc, _ = make()
        wiring._service = self.svc
        self.roles = {}

        def fake_member(ws, uid, min_role="viewer"):
            if uid not in self.roles:
                raise wapi.http_error(WorkspaceError("not_found", "not found", 404))
            return MemberRow(ws, uid, self.roles[uid])

        self._orig = r.require_member
        r.require_member = fake_member
        self.addCleanup(setattr, r, "require_member", self._orig)
        self.addCleanup(setattr, wiring, "_service", None)
        app = FastAPI()
        app.include_router(r.router)
        app.dependency_overrides[r.current_user] = lambda: type("U", (), {"id": U1})()
        self.client = TestClient(app)
        for i in range(3):
            self.svc.record("a.b", U1, {"n": i}, workspace_id=WS)

    def get(self, **params):
        return self.client.get(f"/v1/workspaces/{WS}/audit-log", params=params)

    def test_admin_ok_with_paging(self):
        self.roles[U1] = "admin"
        r = self.get(limit=2)
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual([i["detail"]["n"] for i in body["items"]], [2, 1])
        r2 = self.get(limit=2, cursor=body["next_cursor"]).json()
        self.assertEqual(([i["detail"]["n"] for i in r2["items"]], r2["next_cursor"]), ([0], None))
        self.assertEqual(self.get(**{"from": "2999-01-01T00:00:00Z"}).json()["items"], [])

    def test_non_admin_403_and_non_member_404(self):
        self.roles[U1] = "developer"
        self.assertEqual(self.get().status_code, 403)
        del self.roles[U1]
        self.assertEqual(self.get().status_code, 404)


if __name__ == "__main__":
    unittest.main()

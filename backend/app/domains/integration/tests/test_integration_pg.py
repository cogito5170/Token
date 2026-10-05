"""Provider keys over HTTP on a real PostgreSQL 16 (docs/schema.sql). Skipped without GC_SCHEMA_TEST_DSN, psql,
pg_dump or the runtime deps. The test key and KEK are built at runtime; the KEK lives only in os.environ for the run."""
import base64
import logging
import os
import secrets
import shutil
import subprocess
import tempfile
import unittest
import uuid
from pathlib import Path

DSN = os.environ.get("GC_SCHEMA_TEST_DSN")
REPO = Path(__file__).resolve().parents[5]
try:
    import argon2  # noqa: F401
    import cryptography  # noqa: F401
    import fastapi  # noqa: F401
    import httpx  # noqa: F401
    import multipart  # noqa: F401
    import psycopg  # noqa: F401
    import psycopg_pool  # noqa: F401
    import yaml
    HAVE = True
except ImportError:
    HAVE = False

PW = "pw-" + "Kx7" * 4  # fake test credential, assembled so the secret scan stays clean
WIRINGS = ("identity.router", "workspace.wiring", "audit.wiring", "source.wiring", "ingestion.wiring", "usage.wiring",
           "quota.wiring", "advisor.wiring", "notification.wiring", "profile.wiring", "report.wiring",
           "simulation.wiring", "integration.wiring")
ENV = ("DATABASE_URL", "GC_JWT_SECRET", "GC_UPLOAD_DIR", "GC_KEK_ID", "GC_KEK_pgtest")


def reset_singletons():
    import importlib
    for d in WIRINGS:
        m = importlib.import_module(f"app.domains.{d}")
        if hasattr(m, "_service"):
            m._service = None


def fake_key() -> str:
    """Obviously fake, and shaped so neither the log redactor nor audit's checks would mask a leak."""
    return "gc-test-fake." + secrets.token_hex(12)


def kek() -> str:
    return base64.b64encode(os.urandom(32)).decode()


class Capture(logging.Handler):
    def __init__(self):
        super().__init__(logging.DEBUG)
        self.lines = []

    def emit(self, record):
        self.lines.append(record.getMessage() + (logging.Formatter().formatException(record.exc_info)
                                                 if record.exc_info else "") + (record.exc_text or ""))


@unittest.skipUnless(DSN and HAVE and shutil.which("psql") and shutil.which("pg_dump"),
                     "GC_SCHEMA_TEST_DSN, psql, pg_dump or runtime deps missing")
class ProviderCredentialHttpTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from app.core import db
        cls.name = "gc_integ_" + uuid.uuid4().hex[:8]
        run = lambda dsn, *a: subprocess.run(["psql", dsn, "-v", "ON_ERROR_STOP=1", "-qAt", *a],  # noqa: E731
                                              capture_output=True, text=True, timeout=120)
        assert run(DSN, "-c", f"CREATE DATABASE {cls.name}").returncode == 0
        cls.dsn = DSN.rsplit("/", 1)[0] + "/" + cls.name
        r = run(cls.dsn, "-f", str(REPO / "docs/schema.sql"))
        assert r.returncode == 0, r.stderr
        cls.tmp = tempfile.mkdtemp()
        cls.saved = {k: os.environ.get(k) for k in ENV}
        os.environ.update(DATABASE_URL=cls.dsn, GC_JWT_SECRET="integ-jwt-" + "q" * 24, GC_UPLOAD_DIR=cls.tmp,
                          GC_KEK_ID="pgtest", GC_KEK_pgtest=kek())
        db.close_pool()
        reset_singletons()
        from fastapi.testclient import TestClient
        from app.main import create_app
        cls.client = TestClient(create_app())
        cls.client.__enter__()
        cls.admin = cls.signup("integ-admin@example.com")
        cls.ws = cls.client.get("/v1/workspaces", headers=cls.admin).json()[0]["id"]
        cls.dev = cls.signup("integ-dev@example.com")
        cls.viewer = cls.signup("integ-viewer@example.com")
        cls.outsider = cls.signup("integ-out@example.com")
        for email, role in (("integ-dev@example.com", "developer"), ("integ-viewer@example.com", "viewer")):
            r = cls.client.post(f"/v1/workspaces/{cls.ws}/members", headers=cls.admin, json={"email": email, "role": role})
            assert r.status_code == 201, r.text

    @classmethod
    def tearDownClass(cls):
        from app.core import db
        cls.client.__exit__(None, None, None)
        db.close_pool()
        reset_singletons()
        for k, v in cls.saved.items():
            os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)
        shutil.rmtree(cls.tmp, ignore_errors=True)
        subprocess.run(["psql", DSN, "-qAt", "-c", f"DROP DATABASE IF EXISTS {cls.name} WITH (FORCE)"],
                       capture_output=True)

    @classmethod
    def signup(cls, email):
        r = cls.client.post("/v1/auth/signup", json={"email": email, "password": PW, "display_name": "I"})
        assert r.status_code == 201, r.text
        return {"Authorization": "Bearer " + r.json()["access_token"]}

    def setUp(self):
        self.cap = Capture()
        root = logging.getLogger()
        self.level = root.level
        root.setLevel(logging.DEBUG)
        root.addHandler(self.cap)
        self.addCleanup(root.removeHandler, self.cap)
        self.addCleanup(root.setLevel, self.level)
        self.responses = []

    def call(self, method, path, h, **kw):
        r = self.client.request(method, f"/v1/workspaces/{self.ws}{path}", headers=h, **kw)
        self.responses.append(r)
        return r

    def store(self, key, h=None, provider="anthropic"):
        return self.call("POST", "/provider-credentials", h or self.admin, json={"provider": provider, "secret": key})

    def db_dump(self) -> bytes:
        r = subprocess.run(["pg_dump", "--data-only", self.dsn], capture_output=True, timeout=120)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout

    def row(self, cid):
        r = subprocess.run(["psql", self.dsn, "-qAt", "-c", "SELECT length(ciphertext), length(nonce), length(wrapped_dek), "
                            f"revoked_at IS NOT NULL FROM provider_credentials WHERE id='{cid}'"],
                           capture_output=True, text=True, timeout=60)
        return r.stdout.strip()

    def assert_absent(self, key, texts):
        needles = [key, key[:-4], key.encode().hex(), base64.b64encode(key.encode()).decode()[:-4]]
        for t in texts:
            for n in needles:
                self.assertNotIn(n, t)

    # ---- the rules
    def test_store_list_revoke_never_exposes_the_key(self):
        key = fake_key()
        r = self.store(key)
        self.assertEqual(r.status_code, 201, r.text)
        ref = r.json()
        self.assertEqual(set(ref), {"id", "provider", "fingerprint", "last4", "created_at", "revoked_at"})
        self.assertEqual((ref["provider"], ref["last4"], ref["revoked_at"]), ("anthropic", key[-4:], None))
        self.assertEqual(self.store(key).status_code, 409)                                # duplicate in the workspace
        for h in (self.admin, self.dev, self.viewer):                                       # members list
            lst = self.call("GET", "/provider-credentials", h)
            self.assertEqual(lst.status_code, 200, lst.text)
            self.assertIn(ref["id"], [c["id"] for c in lst.json()])
        self.assertEqual(self.call("GET", "/integrations", self.viewer).json(), [])
        self.assertEqual(self.call("GET", "/provider-credentials", self.outsider).status_code, 404)

        dump = self.db_dump()                                                               # the DB bytes
        self.assertIn(ref["id"].encode(), dump)
        self.assert_absent(key, [dump.decode("utf-8", "replace")])
        self.assertNotIn(key.encode(), dump)

        d = self.call("DELETE", f"/provider-credentials/{ref['id']}", self.admin)
        self.assertEqual(d.status_code, 204, d.text)
        self.assertEqual(self.row(ref["id"]), "0|0|0|t")                                    # ciphertext gone
        self.assertEqual(self.call("DELETE", f"/provider-credentials/{ref['id']}", self.admin).status_code, 404)
        listed = {c["id"]: c for c in self.call("GET", "/provider-credentials", self.admin).json()}
        self.assertIsNotNone(listed[ref["id"]]["revoked_at"])

        audit = self.call("GET", "/audit-log", self.admin)
        self.assertEqual(audit.status_code, 200, audit.text)
        mine = [e for e in audit.json()["items"] if e["target_id"] == ref["id"]]
        self.assertEqual(sorted(e["action"] for e in mine), ["credential.revoke", "credential.store"])
        for e in mine:
            self.assertEqual(e["detail"], {"workspace_id": self.ws, "credential_id": ref["id"]})

        self.assertTrue(any(ref["id"] in line for line in self.cap.lines), "the domain logs ids")
        self.assert_absent(key, [r.text for r in self.responses] + [str(dict(r.headers)) for r in self.responses]
                           + self.cap.lines)

    def test_non_admins_cannot_store_or_revoke(self):
        key = fake_key()
        for h, want in ((self.dev, 403), (self.viewer, 403), (self.outsider, 404)):
            self.assertEqual(self.store(key, h).status_code, want)
        ok = self.store(fake_key())
        self.assertEqual(ok.status_code, 201)
        for h, want in ((self.dev, 403), (self.viewer, 403), (self.outsider, 404)):
            self.assertEqual(self.call("DELETE", f"/provider-credentials/{ok.json()['id']}", h).status_code, want)
        self.assertEqual(self.row(ok.json()["id"]).split("|")[3], "f")
        self.assertNotIn(key.encode(), self.db_dump())
        self.assert_absent(key, [r.text for r in self.responses] + self.cap.lines)

    def test_key_in_a_wrong_field_is_refused_and_not_echoed(self):
        key = fake_key()
        for body in ({"provider": "openai", "secret": fake_key(), "label": key},
                     {"provider": "openai", "secret": fake_key(), key: 1},
                     {"provider": key, "secret": fake_key()},
                     {"provider": "openai", "api_key": key}):
            r = self.call("POST", "/provider-credentials", self.admin, json=body)
            self.assertEqual(r.status_code, 422, r.text)
            self.assertEqual(sorted(r.json()), ["code", "message"])
        r = self.call("POST", "/provider-credentials", {**self.admin, "content-type": "application/json"},
                      content=b'{"provider": "openai", "secret": "' + key.encode() + b'"')
        self.assertEqual(r.status_code, 422)                                                # broken JSON
        self.assertNotIn(key.encode(), self.db_dump())
        self.assert_absent(key, [r.text for r in self.responses] + self.cap.lines)

    def test_wrong_kek_fails_decryption_and_right_kek_reads(self):
        from fastapi import HTTPException
        from app.domains.integration import api, wiring
        key = fake_key()
        cid = self.store(key, provider="openai").json()["id"]
        with api.use_credential(self.ws, cid) as k:
            self.assertEqual(k, key)
        right = os.environ["GC_KEK_pgtest"]
        os.environ["GC_KEK_pgtest"] = kek()
        wiring._service = None
        try:
            with self.assertRaises(HTTPException) as c:
                with api.use_credential(self.ws, cid):
                    self.fail("decrypted under the wrong KEK")
            self.assertEqual(c.exception.status_code, 500)
            self.assertNotIn(key, str(c.exception.detail))
        finally:
            os.environ["GC_KEK_pgtest"] = right
            wiring._service = None
        with api.use_credential(self.ws, cid) as k:
            self.assertEqual(k, key)
        self.assert_absent(key, self.cap.lines)

    def test_no_kek_configured_is_503_and_stores_nothing(self):
        from app.domains.integration import wiring
        key = fake_key()
        saved = os.environ.pop("GC_KEK_ID")
        wiring._service = None
        try:
            r = self.store(key)
        finally:
            os.environ["GC_KEK_ID"] = saved
            wiring._service = None
        self.assertEqual(r.status_code, 503, r.text)
        self.assertNotIn(key.encode(), self.db_dump())
        self.assert_absent(key, [r.text] + self.cap.lines)

    def test_routes_equal_openapi_for_integration(self):
        spec = yaml.safe_load((REPO / "docs/api/openapi.yaml").read_text())
        want = {(p, m) for p, v in spec["paths"].items() if v.get("x-domain") == "integration"
                for m in v if m in ("get", "post", "put", "patch", "delete")}
        got = {(p, m) for p, v in self.client.app.openapi()["paths"].items() for m in v
               if v[m].get("tags") == ["integration"]}
        self.assertEqual(got, want)


if __name__ == "__main__":
    unittest.main()

"""Provider-key rules without a database (MemoryStore, injected keyring/audit/bus). Test keys are fake and built at
runtime; KEK material is random per test. Neither is ever written to a file."""
import base64
import hashlib
import logging
import os
import secrets
import unittest
from dataclasses import replace
from datetime import datetime, timezone

try:
    import cryptography  # noqa: F401
    HAVE = True
except ImportError:
    HAVE = False

WS = "00000000-0000-4000-8000-0000000000a1"
WS2 = "00000000-0000-4000-8000-0000000000b2"
U1 = "00000000-0000-4000-8000-000000000001"
REF_KEYS = {"id", "provider", "fingerprint", "last4", "created_at", "revoked_at"}  # openapi CredentialRef


def fake_key() -> str:
    """Obviously fake; no prefix or 32-char run, so neither the log redactor nor audit's checks would hide a leak."""
    return "gc-test-fake." + secrets.token_hex(12)


def provider_shaped_key() -> str:
    return "sk-" + "ant-" + "FAKE-TEST-" + secrets.token_hex(16)


def kek() -> str:
    return base64.b64encode(os.urandom(32)).decode()


class Capture(logging.Handler):
    def __init__(self):
        super().__init__(logging.DEBUG)
        self.lines = []

    def emit(self, record):
        self.lines.append(self.format(record) + (record.exc_text or ""))


@unittest.skipUnless(HAVE, "cryptography missing")
class Base(unittest.TestCase):
    def setUp(self):
        from app.core.events import EventBus
        from app.domains.integration.crypto import EnvKeyring
        from app.domains.integration.service import IntegrationService, MemoryStore
        self.env = {"GC_KEK_ID": "t1", "GC_KEK_t1": kek()}
        self.keyring = EnvKeyring(self.env)
        self.store = MemoryStore()
        self.audits, self.events = [], []
        self.bus = EventBus()
        for n in ("integration.credential.stored", "integration.credential.revoked"):
            self.bus.subscribe(n, lambda name, p: self.events.append((name, p)))
        self.now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        self.svc = IntegrationService(self.store, self.keyring, publish=self.bus.publish, now=lambda: self.now,
                                      audit=lambda *a, **k: self.audits.append((a, k)))
        self.cap = Capture()
        root = logging.getLogger()
        self.level = root.level
        root.setLevel(logging.DEBUG)
        root.addHandler(self.cap)
        self.addCleanup(root.removeHandler, self.cap)
        self.addCleanup(root.setLevel, self.level)

    def put(self, key=None, ws=WS, provider="anthropic"):
        key = key or fake_key()
        return key, self.svc.store_credential(ws, U1, provider, key)

    def plain(self, ws, cid):
        with self.svc.use_credential(ws, cid) as k:
            return k


class EnvelopeTest(Base):
    def test_roundtrip_and_row_holds_no_plaintext(self):
        key, row = self.put()
        self.assertEqual(self.plain(WS, row.id), key)
        for blob in (row.ciphertext, row.nonce, row.wrapped_dek):
            self.assertNotIn(key.encode(), blob)
            self.assertNotIn(key[:-4].encode(), blob)
        self.assertNotIn(key.encode().hex(), repr(row))
        self.assertEqual((row.kek_id, len(row.nonce)), ("t1", 12))
        self.assertEqual(len(row.ciphertext), len(key) + 16)  # AES-GCM: plaintext length + 16-byte tag

    def test_fresh_dek_and_nonce_per_credential(self):
        key = fake_key()
        _, a = self.put(key, WS)
        _, b = self.put(key, WS2)
        self.assertNotEqual(a.ciphertext, b.ciphertext)
        self.assertNotEqual(a.nonce, b.nonce)
        self.assertNotEqual(a.wrapped_dek[:12], b.wrapped_dek[:12])
        self.assertNotEqual(a.wrapped_dek, b.wrapped_dek)

    def test_secret_is_not_encrypted_with_the_kek_directly(self):
        from cryptography.exceptions import InvalidTag
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        from app.domains.integration.service import _aad
        _, row = self.put()
        with self.assertRaises(InvalidTag):
            AESGCM(self.keyring.kek("t1")).decrypt(row.nonce, row.ciphertext, _aad(WS, row.id, row.provider))

    def test_dek_is_wrapped_by_the_kek(self):
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        from app.domains.integration.crypto import _wrap_aad
        from app.domains.integration.service import _aad
        key, row = self.put()
        aad = _aad(WS, row.id, row.provider)
        dek = AESGCM(self.keyring.kek("t1")).decrypt(row.wrapped_dek[:12], row.wrapped_dek[12:], _wrap_aad("t1", aad))
        self.assertEqual(len(dek), 32)
        self.assertEqual(AESGCM(dek).decrypt(row.nonce, row.ciphertext, aad).decode(), key)

    def test_wrong_kek_fails_decryption(self):
        from app.domains.integration.service import CredentialError
        _, row = self.put()
        self.env["GC_KEK_t1"] = kek()
        with self.assertRaises(CredentialError) as c:
            self.plain(WS, row.id)
        self.assertEqual((c.exception.status, c.exception.code), (500, "decrypt_failed"))

    def test_tampered_ciphertext_fails(self):
        from app.domains.integration.service import CredentialError
        _, row = self.put()
        ct = bytearray(row.ciphertext)
        ct[0] ^= 1
        self.store.rows[row.id] = replace(row, ciphertext=bytes(ct))
        with self.assertRaises(CredentialError):
            self.plain(WS, row.id)

    def test_ciphertext_is_bound_to_its_row(self):
        from app.domains.integration.service import CredentialError
        _, a = self.put()
        _, b = self.put(provider="openai")
        self.store.rows[b.id] = replace(b, ciphertext=a.ciphertext, nonce=a.nonce, wrapped_dek=a.wrapped_dek)
        with self.assertRaises(CredentialError) as c:
            self.plain(WS, b.id)
        self.assertEqual(c.exception.code, "decrypt_failed")
        self.store.rows[a.id] = replace(a, provider="openai")  # same row, other provider: also refused
        with self.assertRaises(CredentialError):
            self.plain(WS, a.id)

    def test_kek_rotation_keeps_old_rows_readable(self):
        key, old = self.put()
        self.env.update(GC_KEK_ID="t2", GC_KEK_t2=kek())
        _, new = self.put()
        self.assertEqual((old.kek_id, new.kek_id), ("t1", "t2"))
        self.assertEqual(self.plain(WS, old.id), key)

    def test_missing_or_bad_kek_refuses_to_store(self):
        from app.domains.integration.service import CredentialError
        for env in ({}, {"GC_KEK_ID": "t1"}, {"GC_KEK_ID": "../x", "GC_KEK_../x": kek()},
                    {"GC_KEK_ID": "t1", "GC_KEK_t1": base64.b64encode(os.urandom(16)).decode()},
                    {"GC_KEK_ID": "t1", "GC_KEK_t1": "not base64!"}):
            self.env.clear()
            self.env.update(env)
            with self.assertRaises(CredentialError) as c:
                self.put()
            self.assertEqual((c.exception.status, c.exception.code), (503, "key_unavailable"))
        self.assertEqual(self.store.rows, {})
        self.assertEqual(self.audits, [])


class FingerprintTest(Base):
    def test_ref_shape_last4_and_fingerprint(self):
        key, row = self.put()
        ref = row.ref()
        self.assertEqual(set(ref), REF_KEYS)
        self.assertEqual(ref["last4"], key[-4:])
        self.assertTrue(ref["fingerprint"].startswith("hmac-sha256:"))
        self.assertNotIn(hashlib.sha256(key.encode()).hexdigest()[:32], ref["fingerprint"])
        self.assertNotIn(key, repr(ref))

    def test_fingerprint_is_keyed_and_workspace_scoped(self):
        from app.domains.integration import crypto
        key = fake_key()
        f1 = crypto.fingerprint(self.keyring, WS, key)
        self.assertEqual(f1, crypto.fingerprint(self.keyring, WS, key))
        self.assertNotEqual(f1, crypto.fingerprint(self.keyring, WS2, key))
        self.assertNotEqual(f1, crypto.fingerprint(self.keyring, WS, fake_key()))
        self.env["GC_KEK_t1"] = kek()
        self.assertNotEqual(f1, crypto.fingerprint(self.keyring, WS, key))

    def test_duplicate_key_in_a_workspace_is_409_until_revoked(self):
        from app.domains.integration.service import CredentialError
        key, row = self.put()
        with self.assertRaises(CredentialError) as c:
            self.put(key)
        self.assertEqual(c.exception.status, 409)
        self.put(key, WS2)
        self.svc.revoke_credential(WS, U1, row.id)
        self.put(key)


class ValidationTest(Base):
    def parse(self, body):
        return self.svc.parse_create(body)

    def test_valid_body_strips_surrounding_whitespace(self):
        key = fake_key()
        self.assertEqual(self.parse({"provider": "openai", "secret": f"  {key}\n"}), ("openai", key))

    def test_key_in_any_other_field_is_refused_without_echo(self):
        from app.domains.integration.service import CredentialError
        key = provider_shaped_key()
        for body in ({"provider": "anthropic", "secret": fake_key(), "label": key},
                     {"provider": "anthropic", "secret": fake_key(), key: "x"},
                     {"provider": key, "secret": fake_key()},
                     {"provider": "anthropic", "api_key": key},
                     [key], key):
            with self.assertRaises(CredentialError) as c:
                self.parse(body)
            self.assertEqual(c.exception.status, 422)
            self.assertNotIn(key, c.exception.message)
            self.assertNotIn(key[-8:], c.exception.message)

    def test_secret_shape(self):
        from app.domains.integration.service import CredentialError, MAX_SECRET, MIN_SECRET
        good = "a" * MIN_SECRET
        self.assertEqual(self.parse({"provider": "slack", "secret": good})[1], good)
        self.assertEqual(len(self.parse({"provider": "slack", "secret": "b" * MAX_SECRET})[1]), MAX_SECRET)
        for bad in ("a" * (MIN_SECRET - 1), "b" * (MAX_SECRET + 1), "abc def ghij klmnop", "abcdefgh\x00ijklmnop",
                    None, 12345678901234567890):
            with self.assertRaises(CredentialError):
                self.parse({"provider": "slack", "secret": bad})

    def test_every_provider_in_the_schema_and_no_other(self):
        from app.domains.integration.service import CredentialError, PROVIDERS
        self.assertEqual(PROVIDERS, ("anthropic", "openai", "gemini", "github", "slack"))
        for p in PROVIDERS:
            self.parse({"provider": p, "secret": fake_key()})
        with self.assertRaises(CredentialError):
            self.parse({"provider": "aws", "secret": fake_key()})


class LifecycleTest(Base):
    def test_audit_and_events_carry_ids_only(self):
        key, row = self.put()
        self.svc.revoke_credential(WS, U1, row.id)
        ids = {"workspace_id": WS, "credential_id": row.id}
        self.assertEqual([a[0] for a in self.audits], [("credential.store", U1, ids), ("credential.revoke", U1, ids)])
        for _, kw in self.audits:
            self.assertEqual(kw, {"workspace_id": WS, "target_kind": "provider_credential", "target_id": row.id})
        self.assertEqual(self.events, [("integration.credential.stored", ids), ("integration.credential.revoked", ids)])

    def test_audit_detail_passes_audits_own_secret_check(self):
        from app.domains.audit.api import AuditService

        class Rows(list):
            def append(self, row):
                super().append(row)
                return row
        rows = Rows()
        self.put()
        args, kw = self.audits[0]
        AuditService(rows).record(*args, **kw)  # raises AuditError on a key-shaped or secret-named detail
        self.assertEqual((rows[0].target_kind, rows[0].workspace_id), ("provider_credential", WS))

    def test_revoke_wipes_ciphertext_and_blocks_use(self):
        from app.domains.integration.service import CredentialError
        _, row = self.put()
        self.svc.revoke_credential(WS, U1, row.id)
        r = self.store.rows[row.id]
        self.assertEqual((r.ciphertext, r.nonce, r.wrapped_dek, r.revoked_at), (b"", b"", b"", self.now))
        self.assertEqual(self.svc.credentials(WS)[0].ref()["revoked_at"], self.now)
        with self.assertRaises(CredentialError) as c:
            self.plain(WS, row.id)
        self.assertEqual(c.exception.status, 404)
        with self.assertRaises(CredentialError) as c:
            self.svc.revoke_credential(WS, U1, row.id)
        self.assertEqual(c.exception.status, 404)
        self.assertEqual(len(self.audits), 2)

    def test_other_workspace_and_bad_ids_are_404(self):
        from app.domains.integration.service import CredentialError
        _, row = self.put()
        for ws, cid in ((WS2, row.id), (WS, "nope"), (WS, "00000000-0000-4000-8000-0000000000ff")):
            with self.assertRaises(CredentialError) as c:
                self.svc.revoke_credential(ws, U1, cid)
            self.assertEqual(c.exception.status, 404)
            with self.assertRaises(CredentialError):
                self.plain(ws, cid)
        self.assertEqual(self.svc.credentials(WS2), [])
        self.assertIsNone(self.store.rows[row.id].revoked_at)

    def test_no_log_record_or_error_contains_the_key(self):
        from app.domains.integration.service import CredentialError
        key, row = self.put()
        self.plain(WS, row.id)
        with self.assertRaises(CredentialError) as dup:
            self.put(key)
        self.env["GC_KEK_t1"] = kek()
        with self.assertRaises(CredentialError) as bad:
            self.plain(WS, row.id)
        self.env.clear()
        with self.assertRaises(CredentialError) as none:
            self.put(key)
        self.assertTrue(self.cap.lines)  # the domain does log; just never the key
        texts = self.cap.lines + [str(e.exception) for e in (dup, bad, none)] + [repr(a) for a in self.audits]
        for t in texts:
            self.assertNotIn(key, t)
            self.assertNotIn(key[:-4], t)

    def test_integrations_list_is_per_workspace(self):
        from app.domains.integration.service import IntegrationRow
        self.store.integ = [IntegrationRow("i1", WS, "github", {}), IntegrationRow("i2", WS2, "slack", {})]
        self.assertEqual([i.id for i in self.svc.integrations(WS)], ["i1"])


if __name__ == "__main__":
    unittest.main()

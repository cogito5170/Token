import json
import unittest

from app.domains.identity import tokens
from app.domains.identity.passwords import PasswordPolicyError, check_policy
from app.domains.identity.service import AuthError, IdentityService, MemoryStore, RateLimiter

SECRET = "-".join(["unit", "test", "signing", "material"])
PW = "correct horse battery"  # fake test password


class FakeHasher:
    def hash(self, p):
        return "fakehash$" + p[::-1]

    def verify(self, h, p):
        return h == self.hash(p)


class Clock:
    def __init__(self):
        self.t = 1_700_000_000.0

    def __call__(self):
        return self.t


def make(**kw):
    clock = Clock()
    audit = []
    events = []
    store = MemoryStore()
    svc = IdentityService(store, FakeHasher(), SECRET, audit=lambda a, u, d: audit.append((a, u, d)),
                          publish=lambda n, p: events.append((n, p)), clock=clock, **kw)
    return svc, store, clock, audit, events


class SignupTest(unittest.TestCase):
    def test_password_never_stored_or_returned(self):
        svc, store, _, audit, events = make()
        t = svc.signup("a@example.com", PW, "A")
        u = store.user_by_email("a@example.com")
        self.assertNotIn(PW, u.password_hash)
        self.assertNotIn(PW, repr(t))
        self.assertNotIn(PW, json.dumps(audit))
        self.assertNotIn(t.refresh_token, [r.token_hash for r in store.refresh.values()])  # only sha256 stored
        self.assertEqual(events[0][0], "identity.user.created")

    def test_duplicate_email_case_insensitive(self):
        svc, *_ = make()
        svc.signup("a@example.com", PW)
        with self.assertRaises(AuthError) as c:
            svc.signup("A@Example.com", PW)
        self.assertEqual(c.exception.status, 409)

    def test_policy(self):
        with self.assertRaises(PasswordPolicyError):
            check_policy("short")
        with self.assertRaises(PasswordPolicyError):
            check_policy("password1234")
        svc, *_ = make()
        with self.assertRaises(AuthError) as c:
            svc.signup("a@example.com", "short")
        self.assertEqual(c.exception.code, "weak_password")


class LoginTest(unittest.TestCase):
    def test_login_ok_and_bad(self):
        svc, _, _, audit, _ = make()
        svc.signup("a@example.com", PW)
        t = svc.login("a@example.com", PW, "1.1.1.1")
        self.assertEqual(t.expires_in, 900)
        with self.assertRaises(AuthError) as c:
            svc.login("a@example.com", "wrong password here", "1.1.1.1")
        self.assertEqual(c.exception.status, 401)
        with self.assertRaises(AuthError):
            svc.login("nobody@example.com", PW, "1.1.1.1")
        self.assertEqual([a for a, _, _ in audit], ["auth.login", "auth.login_failed", "auth.login_failed"])

    def test_11th_login_in_15_min_refused(self):
        svc, _, clock, _, _ = make()
        svc.signup("a@example.com", PW)
        for _ in range(10):
            svc.login("a@example.com", PW, "9.9.9.9")
        with self.assertRaises(AuthError) as c:
            svc.login("a@example.com", PW, "9.9.9.9")
        self.assertEqual((c.exception.status, c.exception.code), (429, "rate_limited"))
        svc.login("a@example.com", PW, "8.8.8.8")  # other IP is separate
        clock.t += 15 * 60 + 1
        svc.login("a@example.com", PW, "9.9.9.9")  # window passed

    def test_limiter_unit(self):
        c = Clock()
        r = RateLimiter(2, 10, clock=c)
        self.assertEqual([r.hit("k"), r.hit("k"), r.hit("k")], [True, True, False])


class RefreshTest(unittest.TestCase):
    def test_rotation(self):
        svc, *_ = make()
        t1 = svc.signup("a@example.com", PW)
        t2 = svc.refresh(t1.refresh_token)
        self.assertNotEqual(t1.refresh_token, t2.refresh_token)
        svc.refresh(t2.refresh_token)

    def test_reuse_revokes_family(self):
        svc, _, _, audit, _ = make()
        t1 = svc.signup("a@example.com", PW)
        t2 = svc.refresh(t1.refresh_token)
        with self.assertRaises(AuthError):
            svc.refresh(t1.refresh_token)  # replay of rotated token
        with self.assertRaises(AuthError):
            svc.refresh(t2.refresh_token)  # descendant is dead too
        self.assertIn("auth.refresh_reuse", [a for a, _, _ in audit])

    def test_other_family_unaffected(self):
        svc, *_ = make()
        svc.signup("a@example.com", PW)
        a = svc.login("a@example.com", PW, "1")
        b = svc.login("a@example.com", PW, "1")
        a2 = svc.refresh(a.refresh_token)
        with self.assertRaises(AuthError):
            svc.refresh(a.refresh_token)
        svc.refresh(b.refresh_token)
        with self.assertRaises(AuthError):
            svc.refresh(a2.refresh_token)

    def test_expired_and_unknown_and_missing(self):
        svc, _, clock, _, _ = make()
        t = svc.signup("a@example.com", PW)
        for bad in (None, "", "nope"):
            with self.assertRaises(AuthError):
                svc.refresh(bad)
        clock.t += tokens.REFRESH_TTL + 1
        with self.assertRaises(AuthError):
            svc.refresh(t.refresh_token)

    def test_logout_revokes(self):
        svc, *_ = make()
        t = svc.signup("a@example.com", PW)
        svc.logout(t.refresh_token)
        with self.assertRaises(AuthError):
            svc.refresh(t.refresh_token)
        svc.logout(None)


class AccessTokenTest(unittest.TestCase):
    def test_expired_jwt_rejected(self):
        svc, _, clock, _, _ = make()
        t = svc.signup("a@example.com", PW)
        self.assertEqual(svc.authenticate(t.access_token).email, "a@example.com")
        clock.t += 15 * 60 + 1
        with self.assertRaises(AuthError) as c:
            svc.authenticate(t.access_token)
        self.assertEqual(c.exception.status, 401)

    def test_tampered_and_wrong_key(self):
        tok = tokens.encode_access(SECRET, "u1", now=1000)
        claims = tokens.decode_access(SECRET, tok, now=1001)
        self.assertEqual(set(claims), {"sub", "iat", "exp", "jti"})
        self.assertEqual(claims["exp"] - claims["iat"], 900)
        with self.assertRaises(tokens.TokenError):
            tokens.decode_access("-".join(["other", "material"]), tok, now=1001)
        h, b, s = tok.split(".")
        with self.assertRaises(tokens.TokenError):
            tokens.decode_access(SECRET, f"{h}.{b}x.{s}", now=1001)
        with self.assertRaises(tokens.TokenError):
            tokens.decode_access(SECRET, "garbage", now=1001)
        none_alg = tokens._b64(b'{"alg":"none"}') + "." + b + "."
        with self.assertRaises(tokens.TokenError):
            tokens.decode_access(SECRET, none_alg, now=1001)
        with self.assertRaises(tokens.TokenError):
            tokens.encode_access("", "u1")


class Argon2Test(unittest.TestCase):
    def test_argon2id(self):
        try:
            import argon2  # noqa: F401
        except ImportError:
            self.skipTest("argon2-cffi not installed")
        from app.domains.identity.passwords import Argon2Hasher
        h = Argon2Hasher()
        x = h.hash(PW)
        self.assertTrue(x.startswith("$argon2id$v=19$m=65536,t=3,p=1$"))
        self.assertTrue(h.verify(x, PW))
        self.assertFalse(h.verify(x, "wrong password here"))
        self.assertFalse(h.verify("not-a-hash", PW))


class RouterTest(unittest.TestCase):
    def test_http_flow(self):
        try:
            from fastapi import FastAPI
            from fastapi.testclient import TestClient
        except ImportError:
            self.skipTest("fastapi not installed")
        from app.domains.identity import router as r
        svc, *_ = make()
        app = FastAPI()
        app.include_router(r.router)
        app.dependency_overrides[r.get_service] = lambda: svc
        c = TestClient(app, base_url="https://testserver")
        res = c.post("/v1/auth/signup", json={"email": "a@example.com", "password": PW})
        self.assertEqual(res.status_code, 201)
        self.assertEqual(set(res.json()), {"access_token", "expires_in"})
        self.assertIn("httponly", res.headers["set-cookie"].lower())
        self.assertIn("samesite=strict", res.headers["set-cookie"].lower())
        me = c.get("/v1/me", headers={"Authorization": "Bearer " + res.json()["access_token"]})
        self.assertEqual(me.json()["email"], "a@example.com")
        self.assertNotIn("password", me.text)
        self.assertEqual(c.get("/v1/me").status_code, 401)
        self.assertEqual(c.post("/v1/auth/refresh").status_code, 200)
        self.assertEqual(c.post("/v1/auth/logout").status_code, 204)


if __name__ == "__main__":
    unittest.main()

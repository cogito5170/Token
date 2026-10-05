"""CMD-GC50: the browser app on another origin needs CORS with credentials, only for GC_CORS_ORIGIN."""
import os
import unittest

try:
    from fastapi.testclient import TestClient
    HAVE = True
except ImportError:
    HAVE = False

ORIGIN = "http://localhost:3000"


def preflight(origin_env):
    from app.main import create_app
    old = os.environ.pop("GC_CORS_ORIGIN", None)
    if origin_env:
        os.environ["GC_CORS_ORIGIN"] = origin_env
    try:
        c = TestClient(create_app())
        return c.options("/v1/auth/signup", headers={"Origin": ORIGIN, "Access-Control-Request-Method": "POST",
                                                      "Access-Control-Request-Headers": "content-type,authorization"})
    finally:
        os.environ.pop("GC_CORS_ORIGIN", None)
        if old is not None:
            os.environ["GC_CORS_ORIGIN"] = old


@unittest.skipUnless(HAVE, "fastapi/httpx not installed")
class CorsTest(unittest.TestCase):
    def test_preflight_allowed_for_configured_origin_with_credentials(self):
        r = preflight(ORIGIN)
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.headers["access-control-allow-origin"], ORIGIN)
        self.assertEqual(r.headers["access-control-allow-credentials"], "true")

    def test_no_cors_headers_without_the_setting(self):
        self.assertNotIn("access-control-allow-origin", preflight(None).headers)

    def test_other_origin_not_allowed(self):
        r = preflight("http://localhost:4000")
        self.assertNotEqual(r.headers.get("access-control-allow-origin"), ORIGIN)


if __name__ == "__main__":
    unittest.main()

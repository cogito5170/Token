"""CMD-GC12 core checks: healthz, redaction, event ordering, import boundary."""
import ast
import logging
import unittest
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "app"


class HealthzTest(unittest.TestCase):
    def test_healthz(self):
        try:
            from fastapi.testclient import TestClient
        except ImportError:
            self.skipTest("fastapi not installed")
        from app.main import create_app
        r = TestClient(create_app()).get("/healthz")
        self.assertEqual((r.status_code, r.json()), (200, {"status": "ok"}))


SAMPLES = {
    "anthropic_key": "sk-ant-api03-abcdefghijklmnop",
    "openai_key": "sk-abcdefghijklmnopqrstuvwx",
    "google_key": "AIzaSyA1234567890abcdefghijklmn",
    "github_token": "ghp_abcdefghijklmnopqrstuvwx",
    "github_pat": "github_pat_abcdefghijklmnopqrstuvwx",
    "aws_key": "AKIAABCDEFGHIJKLMNOP",
    "slack_token": "xoxb-1234567890-abcdef",
    "private_key": "-----BEGIN RSA PRIVATE KEY-----\nMIIE\n-----END RSA PRIVATE KEY-----",
    "jwt": "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.abc123",
    "assign_password": "password=hunter2hunter2",
    "assign_token": "token=abc",
    "assign_secret": "secret=xyz",
    "entropy": "Zm9vYmFyYmF6cXV4MTIzNDU2Nzg5MGFiY2RlZg",
}
SECRET_PART = {
    "assign_password": "hunter2hunter2", "assign_token": "abc", "assign_secret": "xyz",
}


class RedactionTest(unittest.TestCase):
    def test_every_pattern_removed_from_record(self):
        from app.core.logging import RedactionFilter
        for name, s in SAMPLES.items():
            rec = logging.LogRecord("t", logging.INFO, __file__, 1, "got %s here", (s,), None)
            RedactionFilter().filter(rec)
            out = rec.getMessage()
            self.assertIn("[REDACTED", out, name)
            self.assertNotIn(SECRET_PART.get(name, s), out, name)

    def test_exception_text_redacted(self):
        from app.core.logging import RedactionFilter
        try:
            raise ValueError("bad key sk-ant-api03-abcdefghijklmnop")
        except ValueError:
            import sys
            rec = logging.LogRecord("t", logging.ERROR, __file__, 1, "x", None, sys.exc_info())
        RedactionFilter().filter(rec)
        self.assertNotIn("abcdefghijklmnop", rec.exc_text)


class EventBusTest(unittest.TestCase):
    def test_ordered_delivery(self):
        from app.core.events import EventBus
        bus, seen = EventBus(), []
        bus.subscribe("usage.calls.ingested", lambda n, p: seen.append(("a", p["i"])))
        bus.subscribe("usage.calls.ingested", lambda n, p: seen.append(("b", p["i"])))
        for i in range(3):
            bus.publish("usage.calls.ingested", {"i": i})
        self.assertEqual(seen, [("a", 0), ("b", 0), ("a", 1), ("b", 1), ("a", 2), ("b", 2)])

    def test_bad_name_rejected_and_failing_handler_isolated(self):
        from app.core.events import EventBus
        bus, seen = EventBus(), []
        with self.assertRaises(ValueError):
            bus.publish("bad")
        bus.subscribe("a.b.c", lambda n, p: 1 / 0)
        bus.subscribe("a.b.c", lambda n, p: seen.append(1))
        with self.assertLogs("app.core.events", "ERROR"):
            bus.publish("a.b.c")
        self.assertEqual(seen, [1])


def cross_domain_imports(root: Path) -> list[str]:
    """Imports of another domain's module other than its api (or package root) from inside a domain."""
    bad = []
    for f in sorted((root / "domains").rglob("*.py")):
        rel = f.relative_to(root / "domains").parts
        if len(rel) < 2:
            continue
        own = rel[0]
        for node in ast.walk(ast.parse(f.read_text(encoding="utf-8"))):
            names = []
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                names = [node.module] + [f"{node.module}.{a.name}" for a in node.names]
            for n in names:
                p = n.split(".")
                if p[:2] == ["app", "domains"] and len(p) >= 3 and p[2] != own and p[2] in _domains():
                    if len(p) >= 4 and p[3] != "api":
                        bad.append(f"{f.relative_to(root)}: {'.'.join(p[:4])}")
    return sorted(set(bad))


def _domains():
    from app.domains import DOMAINS
    return DOMAINS


class BoundaryTest(unittest.TestCase):
    def test_no_cross_domain_service_imports(self):
        self.assertEqual(cross_domain_imports(APP), [])

    def test_planted_violation_detected(self):
        import shutil
        import tempfile
        with tempfile.TemporaryDirectory() as t:
            root = Path(t) / "app"
            shutil.copytree(APP, root, ignore=shutil.ignore_patterns("__pycache__"))
            (root / "domains" / "usage" / "service.py").write_text(
                "from app.domains.identity.service import hash_password\n", encoding="utf-8")
            self.assertEqual(len(cross_domain_imports(root)), 1)
            (root / "domains" / "usage" / "service.py").write_text(
                "from app.domains.identity.api import current_user\n", encoding="utf-8")
            self.assertEqual(cross_domain_imports(root), [])


if __name__ == "__main__":
    unittest.main()

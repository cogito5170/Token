"""CMD-GC11 done_when: compose, .env.example, secret grep, make targets, CI workflow."""
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from infra import secret_scan

REPO = Path(__file__).resolve().parent.parent.parent


class ComposeTest(unittest.TestCase):
    def test_compose_parses_and_names_postgres16(self):
        text = (REPO / "infra" / "docker-compose.yml").read_text()
        try:
            import yaml
        except ImportError:
            yaml = None
        if yaml:
            doc = yaml.safe_load(text)
            self.assertEqual(doc["services"]["db"]["image"], "postgres:16")
            for s in ("db", "api", "worker", "web"):
                self.assertIn(s, doc["services"])
        else:
            self.assertRegex(text, r"image:\s*postgres:16\b")
            for s in ("db", "api", "worker", "web"):
                self.assertRegex(text, rf"(?m)^  {s}:")


class EnvExampleTest(unittest.TestCase):
    def test_names_only(self):
        names = []
        for line in (REPO / ".env.example").read_text().splitlines():
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            self.assertRegex(line, r"^([A-Z][A-Z0-9_]*|GC_KEK_<id>)=$", f"value present: {line.split('=')[0]}")
            names.append(line[:-1])
        from backend.app.core import config
        for n in config.ENV_VARS:
            self.assertIn(n, names)
        self.assertIn("POSTGRES_PASSWORD", names)


class SecretScanTest(unittest.TestCase):
    def test_finds_planted_key(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "a.env").write_text("GITHUB_TOKEN=ghp_" + "A" * 36 + "\n")
            (Path(d) / "b.py").write_text('API_KEY = "' + "x1" * 12 + '"\n')
            rules = {h[2] for h in secret_scan.scan(d)}
            self.assertIn("github-token", rules)
            self.assertIn("secret-assignment", rules)
            r = subprocess.run([sys.executable, str(REPO / "infra" / "secret_scan.py"), d], capture_output=True, text=True)
            self.assertEqual(r.returncode, 1)
            self.assertNotIn("A" * 36, r.stdout)

    def test_repo_is_clean(self):
        self.assertEqual(secret_scan.scan(REPO), [])


class MakeAndCiTest(unittest.TestCase):
    def test_make_targets(self):
        mk = (REPO / "Makefile").read_text()
        for t in ("db-up", "migrate", "test", "check", "secret-scan"):
            self.assertRegex(mk, rf"(?m)^{t}:")
        self.assertIn("unittest", mk)

    def test_ci_workflow(self):
        wf = (REPO / ".github" / "workflows" / "ci.yml").read_text()
        for needle in ("make check", "make test", "make secret-scan", "postgres:16", "make migrate"):
            self.assertIn(needle, wf)


if __name__ == "__main__":
    unittest.main()

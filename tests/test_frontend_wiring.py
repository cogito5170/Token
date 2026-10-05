"""CMD-FE3: the frontend unit tests are part of `make test` and CI, and vitest never collects Playwright specs."""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class FrontendWiring(unittest.TestCase):
    def test_make_test_runs_frontend_unit_tests(self):
        mk = (ROOT / "Makefile").read_text()
        body = re.search(r"^test:.*?(?=^\S)", mk, re.S | re.M).group(0)
        self.assertIn("npx vitest run", body)
        self.assertIn("npm ci", body)
        self.assertIn("SKIP frontend unit tests", body)

    def test_ci_has_node_for_make_test(self):
        ci = (ROOT / ".github/workflows/ci.yml").read_text()
        self.assertIn("actions/setup-node", ci)

    def test_vitest_excludes_playwright_specs(self):
        cfg = (ROOT / "frontend/vitest.config.ts").read_text()
        self.assertIn('"**/*.spec.ts"', cfg)
        self.assertIn("exclude", cfg)
        self.assertIn('include: ["tests/**/*.test.ts"]', cfg)


if __name__ == "__main__":
    unittest.main()

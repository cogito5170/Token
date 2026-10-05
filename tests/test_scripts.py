"""The other CMD-GC0 scripts: backtest prints a MAPE, openapi validates, work export is valid work/1."""
import json
import re
import subprocess
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
# work/1 as ga-sdk 0.6 checks it (ga/net/pool.py ITEM_KEYS / ITEM_ID at the pinned sha 03e8dae)
ITEM_KEYS = {"schema", "id", "role", "goal", "uses", "needs", "answer", "check", "parent", "depth", "origin"}
ITEM_ID = re.compile(r"^CMD-[A-Z]+\d+$")
ROLES = {"design", "frontend", "core-backend", "ingestion-analytics", "consulting", "infra"}


def run(*args):
    return subprocess.run([sys.executable, *args], cwd=REPO, capture_output=True, text=True, timeout=120)


class ScriptsTest(unittest.TestCase):
    def test_backtest_prints_mape(self):
        r = run("scripts/backtest_estimator.py")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("MAPE tokens", r.stdout)
        last = json.loads(r.stdout.strip().splitlines()[-1])
        self.assertEqual(last["runs"], 100)  # SUMMARY.md: 100 valid runs, void rows excluded
        self.assertGreater(last["baseline"]["tokens"]["mape_pct"], 0)
        self.assertLess(last["baseline"]["tokens"]["mape_pct"], last["naive"]["tokens"]["mape_pct"])

    def test_openapi_validates(self):
        try:
            import jsonschema  # noqa: F401
            import yaml  # noqa: F401
        except ImportError:
            self.skipTest("pyyaml/jsonschema not installed (dev extra)")
        r = run("scripts/validate_openapi.py")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn(", 0 problems", r.stdout)

    def test_export_work_is_work1(self):
        r = run("scripts/export_work.py")
        self.assertEqual(r.returncode, 0, r.stderr)
        items = [json.loads(line) for line in r.stdout.splitlines()]
        self.assertGreaterEqual(len(items), 15)
        seen = set()
        for it in items:
            self.assertLessEqual(set(it), ITEM_KEYS)
            self.assertRegex(it["id"], ITEM_ID)
            self.assertIn(it["role"], ROLES)
            self.assertTrue(it["goal"].strip())
            self.assertTrue(isinstance(it["check"], list) and all(isinstance(x, str) for x in it["check"]))
            seen.add(it["id"])
        self.assertEqual({i["role"] for i in items}, ROLES)


    def test_export_work_unknown_dependency(self):
        import shutil
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            shutil.copytree(REPO / "scripts", root / "scripts", ignore=shutil.ignore_patterns("__pycache__"))
            (root / "docs").mkdir()
            text = (REPO / "docs" / "roadmap.md").read_text(encoding="utf-8")
            (root / "docs" / "roadmap.md").write_text(
                text.replace('"depends_on": ["CMD-GC10"]', '"depends_on": ["CMD-NOPE1"]', 1), encoding="utf-8")
            r = subprocess.run([sys.executable, "scripts/export_work.py"], cwd=root, capture_output=True, text=True)
            self.assertEqual(r.returncode, 2)
            self.assertIn("unknown item 'CMD-NOPE1'", r.stderr)
            self.assertNotIn("Traceback", r.stderr)


if __name__ == "__main__":
    unittest.main()

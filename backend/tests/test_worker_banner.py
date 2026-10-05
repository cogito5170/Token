"""Acceptance test for CMD-AGA1 (written by baseline; the executor may not edit it)."""
import ast
import unittest
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "app" / "worker" / "__main__.py"


class WorkerBanner(unittest.TestCase):
    def test_banner_says_ready_and_names_the_worker(self):
        from app.worker.__main__ import banner
        line = banner("host:42", 1.0)
        self.assertIsInstance(line, str)
        self.assertIn("worker ready", line)
        self.assertIn("host:42", line)
        self.assertNotIn("\n", line.strip())

    def test_main_prints_the_banner_with_flush(self):
        tree = ast.parse(SRC.read_text(encoding="utf-8"))
        main = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "main")
        prints = [n for n in ast.walk(main) if isinstance(n, ast.Call) and getattr(n.func, "id", "") == "print"]
        self.assertTrue(any(any(isinstance(a, ast.Call) and getattr(a.func, "id", "") == "banner" for a in c.args)
                            and any(k.arg == "flush" for k in c.keywords) for c in prints),
                        "main() must print(banner(...), flush=True) once it is ready")


if __name__ == "__main__":
    unittest.main()

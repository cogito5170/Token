"""Skeleton checks (CMD-GC0): every domain package imports and declares the tables docs/domain-model.md gives it."""
import importlib
import re
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def doc_tables() -> dict[str, list[str]]:
    text = (REPO / "docs" / "domain-model.md").read_text(encoding="utf-8")
    out = {}
    for d, body in re.findall(r"^## `(\w+)` — .+?$(.*?)(?=^## `|\Z)", text, re.M | re.S):
        line = re.search(r"^- owned_tables: (.*)$", body, re.M).group(1)
        out[d] = re.findall(r"`(\w+)`", line)
    return out


class SkeletonTest(unittest.TestCase):
    def test_domains_match_docs(self):
        from app.domains import DOMAINS
        self.assertEqual(list(DOMAINS), list(doc_tables()))

    def test_owned_tables_match_docs(self):
        for d, tables in doc_tables().items():
            mod = importlib.import_module(f"app.domains.{d}")
            self.assertEqual(mod.DOMAIN, d)
            self.assertEqual(list(mod.OWNED_TABLES), tables, d)

    def test_provenance_matches_schema(self):
        from app.core.provenance import Provenance, weaker
        sql = (REPO / "docs" / "schema.sql").read_text(encoding="utf-8")
        enum = re.search(r"CREATE TYPE provenance AS ENUM \((.*?)\);", sql).group(1)
        self.assertEqual([p.value for p in Provenance], re.findall(r"'(\w+)'", enum))
        self.assertIs(weaker(Provenance.MEASURED, Provenance.ESTIMATED), Provenance.ESTIMATED)

    def test_app_imports_without_runtime_deps(self):
        importlib.import_module("app.main")
        importlib.import_module("app.worker")


if __name__ == "__main__":
    unittest.main()

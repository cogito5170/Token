"""Contract v0.1 materialized (CMD-GC10): migrations equal docs/schema.sql, apply to an empty PostgreSQL,
and no OpenAPI response schema carries a secret-bearing field."""
import os
import re
import shutil
import subprocess
import unittest
import uuid
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent.parent
MIGRATIONS = REPO / "backend" / "migrations"
DSN = os.environ.get("GC_SCHEMA_TEST_DSN")

SECRET_NAME = re.compile(r"(password|secret|api_?key|private_?key|ciphertext|refresh_token|credential_value|^key_value$)", re.I)
# Documented exceptions: the access token is the one credential a response may carry (login/refresh/register).
ALLOWED = {("TokenPair", "access_token")}


def migration_files():
    return sorted(MIGRATIONS.glob("[0-9][0-9][0-9][0-9]_*.sql"))


class MigrationFileTest(unittest.TestCase):
    def test_init_equals_schema(self):
        self.assertEqual((MIGRATIONS / "0001_init.sql").read_bytes(), (REPO / "docs" / "schema.sql").read_bytes())

    def test_numbering_contiguous(self):
        nums = [int(p.name[:4]) for p in migration_files()]
        self.assertEqual(nums, list(range(1, len(nums) + 1)))


@unittest.skipUnless(DSN and shutil.which("psql"), "GC_SCHEMA_TEST_DSN not set or psql missing")
class MigrationApplyTest(unittest.TestCase):
    def psql(self, dsn, *args):
        return subprocess.run(["psql", dsn, "-v", "ON_ERROR_STOP=1", "-qAt", *args],
                              capture_output=True, text=True, timeout=120)

    def test_all_migrations_apply_to_empty_db(self):
        name = "gc_mig_" + uuid.uuid4().hex[:8]
        r = self.psql(DSN, "-c", f"CREATE DATABASE {name}")
        self.assertEqual(r.returncode, 0, r.stderr)
        try:
            db = DSN.rsplit("/", 1)[0] + "/" + name
            for f in migration_files():
                r = self.psql(db, "-f", str(f))
                self.assertEqual(r.returncode, 0, f"{f.name}: {r.stderr}")
            r = self.psql(db, "-c", "select count(*) from information_schema.tables where table_schema='public'")
            self.assertGreater(int(r.stdout.strip()), 0)
        finally:
            self.psql(DSN, "-c", f"DROP DATABASE IF EXISTS {name}")


class NoSecretInResponsesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.spec = yaml.safe_load((REPO / "docs" / "api" / "openapi.yaml").read_text(encoding="utf-8"))
        cls.schemas = cls.spec["components"]["schemas"]

    def walk(self, node, owner, seen, found):
        if isinstance(node, list):
            for n in node:
                self.walk(n, owner, seen, found)
        elif isinstance(node, dict):
            ref = node.get("$ref")
            if ref:
                name = ref.rsplit("/", 1)[-1]
                if name in seen:
                    return
                seen.add(name)
                self.walk(self.schemas[name], name, seen, found)
                return
            for prop in (node.get("properties") or {}):
                if SECRET_NAME.search(prop) and (owner, prop) not in ALLOWED:
                    found.append(f"{owner}.{prop}")
            for k, v in node.items():
                if k != "properties":
                    self.walk(v, owner, seen, found)
            for sub in (node.get("properties") or {}).values():
                self.walk(sub, owner, seen, found)

    def test_response_schemas_have_no_secret_fields(self):
        found, responses = [], 0
        for path, item in self.spec["paths"].items():
            for method, op in item.items():
                if not isinstance(op, dict) or "responses" not in op:
                    continue
                for code, resp in op["responses"].items():
                    responses += 1
                    self.walk(resp, f"{method.upper()} {path} {code}", set(), found)
        self.assertGreater(responses, 0)
        self.assertEqual(found, [])

    def test_detector_catches_planted_secret(self):
        self.schemas["__Planted"] = {"type": "object", "properties": {"api_key": {"type": "string"}}}
        try:
            found = []
            self.walk({"$ref": "#/components/schemas/__Planted"}, "x", set(), found)
            self.assertEqual(found, ["__Planted.api_key"])
        finally:
            del self.schemas["__Planted"]


if __name__ == "__main__":
    unittest.main()

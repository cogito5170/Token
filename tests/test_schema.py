"""docs/schema.sql applies to an empty PostgreSQL (CMD-GC0 D1).

Set GC_SCHEMA_TEST_DSN to a server where the user may CREATE DATABASE (e.g. postgresql://localhost/postgres).
Without it the test is skipped, and says so.
"""
import os
import shutil
import subprocess
import unittest
import uuid
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DSN = os.environ.get("GC_SCHEMA_TEST_DSN")


@unittest.skipUnless(DSN and shutil.which("psql"), "GC_SCHEMA_TEST_DSN not set or psql missing")
class SchemaTest(unittest.TestCase):
    def psql(self, dsn, *args, **kw):
        return subprocess.run(["psql", dsn, "-v", "ON_ERROR_STOP=1", "-qAt", *args],
                              capture_output=True, text=True, timeout=120, **kw)

    def test_applies_to_empty_db(self):
        name = "gc_schema_" + uuid.uuid4().hex[:8]
        r = self.psql(DSN, "-c", f"CREATE DATABASE {name}")
        self.assertEqual(r.returncode, 0, r.stderr)
        try:
            db = DSN.rsplit("/", 1)[0] + "/" + name
            r = self.psql(db, "-f", str(REPO / "docs" / "schema.sql"))
            self.assertEqual(r.returncode, 0, r.stderr)
            r = self.psql(db, "-c", "select count(*) from information_schema.tables where table_schema='public'")
            self.assertEqual(int(r.stdout.strip()), 43)
            r = self.psql(db, "-c", "insert into audit_log(actor_kind, action, target_kind, target_id) "
                                    "values ('system','t','t','1'); update audit_log set action='x'")
            self.assertNotEqual(r.returncode, 0)  # append-only trigger
            self.assertIn("append-only", r.stderr)
        finally:
            self.psql(DSN, "-c", f"DROP DATABASE IF EXISTS {name}")


if __name__ == "__main__":
    unittest.main()

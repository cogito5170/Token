"""profile on a real PostgreSQL 16 (docs/schema.sql). Skipped without GC_SCHEMA_TEST_DSN, psql or psycopg."""
import os
import shutil
import subprocess
import unittest
import uuid
from pathlib import Path

from app.domains.profile.service import ProfileService

DSN = os.environ.get("GC_SCHEMA_TEST_DSN")
REPO = Path(__file__).resolve().parents[5]
try:
    import psycopg  # noqa: F401
    import psycopg_pool
except ImportError:
    psycopg = None


def _task(model, outcome):
    return {"kind": "feature", "model_primary": model, "outcome": outcome, "total_tokens": 1000,
            "cost_list_microusd": 1000, "cost_cli_microusd": None, "structure": "single", "context_mode": "selective"}


@unittest.skipUnless(DSN and shutil.which("psql") and psycopg, "GC_SCHEMA_TEST_DSN, psql or psycopg missing")
class PgProfileTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.name = "gc_profile_" + uuid.uuid4().hex[:8]
        run = lambda dsn, *a: subprocess.run(["psql", dsn, "-v", "ON_ERROR_STOP=1", "-qAt", *a],  # noqa: E731
                                              capture_output=True, text=True, timeout=120)
        assert run(DSN, "-c", f"CREATE DATABASE {cls.name}").returncode == 0
        cls.dsn = DSN.rsplit("/", 1)[0] + "/" + cls.name
        r = run(cls.dsn, "-f", str(REPO / "docs" / "schema.sql"))
        assert r.returncode == 0, r.stderr
        cls.pool = psycopg_pool.ConnectionPool(cls.dsn, min_size=1, max_size=3, open=True)
        with cls.pool.connection() as c:
            mk = lambda e: str(c.execute("INSERT INTO users (email, display_name, password_hash) VALUES (%s,'a','x') "  # noqa: E731
                                         "RETURNING id", (e,)).fetchone()[0])
            cls.u1, cls.u2 = mk("a@example.com"), mk("b@example.com")
            cls.ws = str(c.execute("INSERT INTO workspaces (name, slug, created_by) VALUES ('w','w',%s) RETURNING id",
                                   (cls.u1,)).fetchone()[0])
            for m in ("m-a", "m-b"):
                c.execute("INSERT INTO models (id, provider, family, tier, min_cache_tokens, display_name) "
                          "VALUES (%s,'anthropic','claude',2,1,%s)", (m, m))

    @classmethod
    def tearDownClass(cls):
        cls.pool.close()
        subprocess.run(["psql", DSN, "-qAt", "-c", f"DROP DATABASE {cls.name} WITH (FORCE)"], capture_output=True)

    def test_roundtrip(self):
        from app.domains.profile.pg_store import PgStore
        tasks = [_task("m-a", "correct" if i < 4 else "incorrect") for i in range(6)]
        tasks += [_task("m-b", "correct") for _ in range(5)]
        proposals = []
        s = ProfileService(PgStore(self.pool), lambda ws: tasks,
                           lambda *a: proposals.append(a) or {"id": str(uuid.uuid4())})
        self.assertIs(s.get_profile(self.ws, self.u1)["store_bodies"], False)
        s.put_profile(self.ws, self.u1, {"quality_floor_permille": 800, "preferred_models": ["m-b"], "team_size": 2})
        s.put_profile(self.ws, self.u1, {"quality_floor_permille": 800, "preferred_models": ["m-b"], "team_size": 3})
        self.assertEqual(s.get_profile(self.ws, self.u1)["team_size"], 3)
        s.refresh_stats(self.ws)
        self.assertEqual(len(s.stats(self.ws, self.u1)), 2)
        self.assertEqual(s.stats(self.ws, self.u2), [])
        recs = s.recommendations(self.ws, self.u1)
        self.assertEqual(len(recs), 1)
        self.assertEqual(recs[0]["evidence_n"], 5)
        s.to_proposal(self.ws, self.u1, recs[0]["id"])
        self.assertIsNotNone(s.recommendations(self.ws, self.u1)[0]["proposal_id"])
        s.refresh_stats(self.ws)
        self.assertEqual(s.store.stats(self.ws, self.u1)[0].version, 2)


if __name__ == "__main__":
    unittest.main()

"""CMD-GC50 D1: scripts/dev_env.py, the config dump, and compose/frontend env-name agreement."""
import base64
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO / "backend"))
import dev_env  # noqa: E402

SCRIPT = REPO / "scripts" / "dev_env.py"
EXAMPLE = REPO / ".env.example"


def parse(path: Path) -> dict[str, str]:
    return dict(l.split("=", 1) for l in path.read_text().splitlines() if l and not l.startswith("#"))


def run(*args):
    return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True)


class DevEnvTest(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.TemporaryDirectory()
        self.addCleanup(self.d.cleanup)
        self.path = Path(self.d.name) / ".env"

    def test_writes_every_example_name_except_the_pattern_line(self):
        r = run("--path", str(self.path))
        self.assertEqual(r.returncode, 0, r.stderr)
        got = parse(self.path)
        names = dev_env.example_names(EXAMPLE.read_text())
        self.assertIn("GC_KEK_ID", names)
        for n in names:
            self.assertTrue(got.get(n), f"{n} missing or empty")
        self.assertNotIn("GC_KEK_<id>", got)
        self.assertEqual(got["NEXT_PUBLIC_API_MODE"], "real")
        self.assertEqual(got["NEXT_PUBLIC_API_URL"], "http://localhost:8000")
        self.assertEqual(got["GC_CORS_ORIGIN"], "http://localhost:3000")
        self.assertTrue(got["DATABASE_URL"].startswith("postgresql://gaconsole:" + got["POSTGRES_PASSWORD"] + "@db:5432/"))

    def test_kek_named_by_kek_id_decodes_to_32_bytes(self):
        run("--path", str(self.path))
        got = parse(self.path)
        self.assertEqual(got["GC_KEK_ID"], "dev")
        self.assertEqual(len(base64.b64decode(got["GC_KEK_" + got["GC_KEK_ID"]], validate=True)), 32)

    def test_refuses_to_overwrite_an_existing_env(self):
        self.path.write_text("KEEP=me\n")
        r = run("--path", str(self.path))
        self.assertNotEqual(r.returncode, 0)
        self.assertEqual(self.path.read_text(), "KEEP=me\n")
        with self.assertRaises(SystemExit):
            dev_env.write_env(self.path)
        self.assertEqual(self.path.read_text(), "KEEP=me\n")

    def test_never_prints_a_value(self):
        r = run("--path", str(self.path))
        shown = r.stdout + r.stderr
        self.assertIn("GC_JWT_SECRET", shown)  # names are fine
        for n, v in parse(self.path).items():
            if n in ("GC_KEK_ID", "GC_UPLOAD_MAX_BYTES") or v.startswith("http") or v in ("real", "/data/uploads"):
                continue  # fixed, non-secret settings
            self.assertNotIn(v, shown, f"value of {n} printed")
        self.path.unlink()
        r2 = run("--path", str(self.path), "--db-host", "localhost")  # a refusal prints no value either
        r3 = run("--path", str(self.path))
        for v in parse(self.path).values():
            if len(v) > 20:
                self.assertNotIn(v, r2.stdout + r3.stdout + r3.stderr)

    def test_values_differ_between_runs_and_file_is_private(self):
        other = Path(self.d.name) / "b.env"
        run("--path", str(self.path))
        run("--path", str(other))
        a, b = parse(self.path), parse(other)
        for n in ("GC_JWT_SECRET", "POSTGRES_PASSWORD", "TELEMETRY_HASH_KEY", "GC_KEK_dev"):
            self.assertNotEqual(a[n], b[n], n)
        self.assertEqual(self.path.stat().st_mode & 0o077, 0)

    def test_env_stays_git_ignored_and_no_env_is_committed(self):
        self.assertIn(".env", (REPO / ".gitignore").read_text().splitlines())
        tracked = subprocess.run(["git", "ls-files"], cwd=REPO, capture_output=True, text=True).stdout.split()
        self.assertNotIn(".env", tracked)


class MakeTest(unittest.TestCase):
    def test_make_dev_targets(self):
        mk = (REPO / "Makefile").read_text()
        dev = re.search(r"^dev:.*?(?=^\S)", mk, re.S | re.M).group(0)
        self.assertIn("dev-env", dev.splitlines()[0])
        for part in ("up -d --wait db", "dev-migrate", "up -d api worker web"):
            self.assertIn(part, dev)
        self.assertRegex(mk, r"(?m)^dev-env:.*\n\t@test -f \.env \|\| \$\(PY\) scripts/dev_env\.py")
        self.assertRegex(mk, r"(?m)^dev-down:.*\n\t\$\(COMPOSE\) down")


class ConfigDumpTest(unittest.TestCase):
    def test_dump_hides_every_kek_variable_and_redacts_secrets(self):
        from app.core import config
        env = {"GC_KEK_ID": "dev", "GC_KEK_dev": "KEKMATERIAL", "GC_KEK_other": "MORE", "GC_JWT_SECRET": "JWTVALUE",
               "DATABASE_URL": "postgresql://u:PGPASS@h/db", "GC_CORS_ORIGIN": "http://localhost:3000", "PATH": "/bin"}
        out = config.dump(env)
        self.assertFalse([k for k in out if k.startswith("GC_KEK_")])
        text = repr(out)
        for secret in ("KEKMATERIAL", "MORE", "JWTVALUE", "PGPASS"):
            self.assertNotIn(secret, text)
        self.assertEqual(out["GC_CORS_ORIGIN"], "http://localhost:3000")
        self.assertNotIn("PATH", out)


class ComposeNamesTest(unittest.TestCase):
    def setUp(self):
        self.text = (REPO / "infra" / "docker-compose.yml").read_text()

    def test_web_uses_the_names_the_code_reads(self):
        used = set()
        for p in (REPO / "frontend" / "src").rglob("*.ts*"):
            used |= set(re.findall(r"process\.env\.(NEXT_PUBLIC_[A-Z_]+)", p.read_text()))
        self.assertEqual(used, {"NEXT_PUBLIC_API_MODE", "NEXT_PUBLIC_API_URL"})
        compose = set(re.findall(r"NEXT_PUBLIC_[A-Z_]+", self.text))
        self.assertEqual(compose, used, "compose and frontend code must use the same names")
        example = set(dev_env.example_names(EXAMPLE.read_text()))
        self.assertTrue(used <= example)

    def test_web_defaults_to_real(self):
        self.assertRegex(self.text, r"NEXT_PUBLIC_API_MODE:\s*\$\{NEXT_PUBLIC_API_MODE:-real\}")

    def test_backend_gets_every_backend_name(self):
        from app.core import config
        for n in config.ENV_VARS:
            self.assertRegex(self.text, rf"(?m)^\s+{n}:", n)
        self.assertRegex(self.text, r"(?m)^\s+GC_KEK_dev:")

    def test_example_documents_the_kek_pattern(self):
        self.assertIn("GC_KEK_<id>=", EXAMPLE.read_text())


if __name__ == "__main__":
    unittest.main()

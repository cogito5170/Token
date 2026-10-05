#!/usr/bin/env python3
"""Browser e2e on the real stack, without Docker (CMD-GC50).

Creates a throwaway database on the PostgreSQL named by DATABASE_URL (a role that may CREATE DATABASE), applies
docs/schema.sql, starts api (uvicorn), worker and web (next build + start) with generated fake secrets, waits for
health, runs tests/e2e/gc50.spec.ts with Playwright, then stops everything and drops the database.

  DATABASE_URL=postgresql://postgres:...@127.0.0.1:5432/postgres python3 scripts/e2e_stack.py

Needs the backend installed in this interpreter (pip install -e backend), node + frontend/node_modules, psql, and a
Chromium (PLAYWRIGHT_CHROMIUM_PATH, default /opt/pw-browsers/chromium*/chrome-linux/chrome if present).
Exit codes: 0 passed or skipped (reason printed), 1 failed.
"""
from __future__ import annotations

import base64
import glob
import importlib.util
import os
import secrets
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FRONTEND = ROOT / "frontend"
E2E = ROOT / "tests" / "e2e"
PINNED = (("telemetry.collect", "l0-telemetry"), ("rlo", "rlo-sdk"))


def missing_pins() -> str | None:
    gone = []
    for mod, dist in PINNED:
        try:
            ok = importlib.util.find_spec(mod) is not None
        except (ImportError, ValueError):
            ok = False
        if not ok:
            gone.append(dist)
    return ("pinned parser packages not installed: " + ", ".join(gone)) if gone else None


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def wait_http(url: str, timeout: float = 180) -> None:
    end = time.time() + timeout
    while time.time() < end:
        try:
            with urllib.request.urlopen(url, timeout=3) as r:
                if r.status < 500:
                    return
        except Exception:
            time.sleep(0.5)
    raise SystemExit(f"timeout waiting for {url}")


def psql(dsn: str, *args: str) -> None:
    subprocess.run(["psql", dsn, "-v", "ON_ERROR_STOP=1", "-qAt", *args], check=True, capture_output=True, text=True, timeout=120)


def chromium() -> str | None:
    if os.environ.get("PLAYWRIGHT_CHROMIUM_PATH"):
        return os.environ["PLAYWRIGHT_CHROMIUM_PATH"]
    hits = sorted(glob.glob("/opt/pw-browsers/chromium-*/chrome-linux/chrome"))
    return hits[-1] if hits else None


def main() -> int:
    admin = os.environ.get("DATABASE_URL")
    if not admin:
        raise SystemExit("DATABASE_URL is not set (an admin DSN; a throwaway database is created on it)")
    reason = missing_pins()
    env_skip = reason or ""
    db = "gc_e2e_" + secrets.token_hex(4)
    dsn = admin.rsplit("/", 1)[0] + "/" + db
    api_port, web_port = free_port(), free_port()
    api_url, web_url = f"http://localhost:{api_port}", f"http://localhost:{web_port}"
    tmp = tempfile.mkdtemp(prefix="gc-e2e-")
    base = {k: v for k, v in os.environ.items() if k != "DATABASE_URL"}
    shots = ROOT / "reports" / "gc50"
    shots.mkdir(parents=True, exist_ok=True)
    backend_env = {
        **base,
        "DATABASE_URL": dsn,
        "GC_JWT_SECRET": secrets.token_urlsafe(48),
        "GC_KEK_ID": "e2e",
        "GC_KEK_e2e": base64.b64encode(secrets.token_bytes(32)).decode(),
        "TELEMETRY_HASH_KEY": secrets.token_urlsafe(32),
        "GC_UPLOAD_DIR": tmp,
        "GC_CORS_ORIGIN": web_url,
    }
    web_env = {**base, "NEXT_PUBLIC_API_MODE": "real", "NEXT_PUBLIC_API_URL": api_url}
    procs: list[subprocess.Popen] = []
    code = 1
    created = False
    try:
        psql(admin, "-c", f"CREATE DATABASE {db}")
        created = True
        psql(dsn, "-f", str(ROOT / "docs" / "schema.sql"))
        log = open(Path(tmp) / "stack.log", "ab")
        spawn = lambda cmd, env, cwd: procs.append(subprocess.Popen(  # noqa: E731
            cmd, cwd=cwd, env=env, stdout=log, stderr=subprocess.STDOUT, start_new_session=True))
        spawn([sys.executable, "-m", "uvicorn", "app.main:create_app", "--factory", "--port", str(api_port)], backend_env, ROOT / "backend")
        spawn([sys.executable, "-m", "app.worker"], backend_env, ROOT / "backend")
        wait_http(api_url + "/healthz", 60)
        subprocess.run(["npx", "next", "build"], cwd=FRONTEND, env=web_env, check=True, stdout=log, stderr=subprocess.STDOUT, timeout=900)
        spawn(["npx", "next", "start", "-p", str(web_port)], web_env, FRONTEND)
        wait_http(web_url + "/login", 60)

        link = E2E / "node_modules"  # lets the spec resolve @playwright/test from frontend/node_modules
        if not link.exists():
            link.symlink_to(FRONTEND / "node_modules")
        run_env = {**base, "E2E_WEB_URL": web_url, "E2E_API_URL": api_url, "E2E_SHOTS": str(shots), "E2E_SKIP_REASON": env_skip}
        exe = chromium()
        if exe:
            run_env["PLAYWRIGHT_CHROMIUM_PATH"] = exe
        r = subprocess.run(["npx", "playwright", "test", "-c", str(E2E / "playwright.config.ts")], cwd=FRONTEND, env=run_env)
        code = r.returncode
        if code:
            print("stack log:", Path(tmp) / "stack.log", file=sys.stderr)
        print("e2e skipped: " + env_skip if env_skip else f"e2e finished: exit {code}")
    finally:
        for p in procs:
            try:
                os.killpg(p.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
        for p in procs:
            try:
                p.wait(timeout=15)
            except subprocess.TimeoutExpired:
                os.killpg(p.pid, signal.SIGKILL)
        if created:
            subprocess.run(["psql", admin, "-qAt", "-c", f"DROP DATABASE IF EXISTS {db} WITH (FORCE)"], capture_output=True)
        if code == 0:
            shutil.rmtree(tmp, ignore_errors=True)
    return code


if __name__ == "__main__":
    sys.exit(main())

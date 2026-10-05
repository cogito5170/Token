"""`python -m app.worker`: claim ingest_jobs (SKIP LOCKED) and run the pipeline until stopped."""
from __future__ import annotations

import os
import signal
import socket
import time

POLL_S = 1.0


def banner(me: str, poll_s: float) -> str:
    """Return a one‑line status message indicating the worker is ready.

    The message includes the phrase ``worker ready`` and the worker's name
    ``me``.  Optionally it can mention the poll interval ``poll_s``.
    """
    return f"worker ready – {me} (poll every {poll_s}s)"


def main() -> None:
    from app.core.config import load_settings
    from app.core.db import open_pool
    from app.api.wiring import wire_worker
    from app.domains.ingestion.wiring import get_service

    s = load_settings()
    if not s.database_url:
        raise SystemExit("DATABASE_URL is not set")
    open_pool(s.database_url)
    wire_worker()
    svc = get_service()
    me = f"{socket.gethostname()}:{os.getpid()}"
    print(banner(me, POLL_S), flush=True)
    stop = []
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda *_: stop.append(1))
    while not stop:
        if not svc.run_one(me):
            time.sleep(POLL_S)


if __name__ == "__main__":
    main()

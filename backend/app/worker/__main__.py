"""`python -m app.worker`: claim ingest_jobs (SKIP LOCKED) and run the pipeline until stopped."""
from __future__ import annotations

import os
import signal
import socket
import time

POLL_S = 1.0


def main() -> None:
    from app.core.config import load_settings
    from app.core.db import open_pool
    from app.domains.ingestion.wiring import get_service

    s = load_settings()
    if not s.database_url:
        raise SystemExit("DATABASE_URL is not set")
    open_pool(s.database_url)
    svc = get_service()
    me = f"{socket.gethostname()}:{os.getpid()}"
    stop = []
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda *_: stop.append(1))
    while not stop:
        if not svc.run_one(me):
            time.sleep(POLL_S)


if __name__ == "__main__":
    main()

"""ASGI entry point: create_app() assembles every domain router, the process wiring and the error handlers."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

log = logging.getLogger(__name__)


def create_app():
    from fastapi import FastAPI

    from app.api import build_router, errors, wiring
    from app.core import logging as core_logging
    from app.core.config import load_settings
    from app.core.db import close_pool, open_pool

    core_logging.install()

    @asynccontextmanager
    async def lifespan(app):
        dsn = load_settings().database_url
        if dsn:
            open_pool(dsn)
        else:
            log.warning("DATABASE_URL is not set: only /healthz works")
        try:
            yield
        finally:
            close_pool()

    app = FastAPI(title="ga Console", lifespan=lifespan)
    errors.install(app)

    @app.get("/healthz")
    def healthz():
        return {"status": "ok"}

    app.include_router(build_router())
    wiring.wire_api()
    return app


app = None  # `uvicorn app.main:create_app --factory`

"""ASGI entry point: create_app() with /healthz and the assembled domain routers."""
from __future__ import annotations


def create_app():
    from fastapi import FastAPI

    from app.api import build_router
    from app.core import logging as core_logging

    core_logging.install()
    app = FastAPI(title="ga Console")

    @app.get("/healthz")
    def healthz():
        return {"status": "ok"}

    app.include_router(build_router())
    return app


app = None  # `uvicorn app.main:create_app --factory`

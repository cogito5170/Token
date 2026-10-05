"""ASGI entry point. Skeleton only (CMD-GC0): CMD-GC12 builds create_app() with /healthz and the domain routers."""


def create_app():
    from fastapi import FastAPI  # imported here so the skeleton imports without the runtime dependencies

    return FastAPI(title="ga Console")

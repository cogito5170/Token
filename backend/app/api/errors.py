"""One exception handler set: every error body is {"code", "message"} at the top level (CMD-GC13 request).

Domains raise HTTPException(detail={"code", "message"}); FastAPI would wrap that as {"detail": {...}}. Here the dict
is unwrapped. Validation errors never echo the offending input (it may hold a secret): only the field path and the
validator's message.
"""
from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

log = logging.getLogger(__name__)
_CODES = {400: "invalid_request", 401: "unauthorized", 403: "forbidden", 404: "not_found", 405: "method_not_allowed",
          409: "conflict", 413: "payload_too_large", 415: "unsupported_media_type", 422: "invalid_request",
          429: "rate_limited"}


def error_body(code: str, message: str) -> dict:
    return {"code": code, "message": message}


async def _http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    d = exc.detail
    if isinstance(d, dict) and isinstance(d.get("code"), str) and isinstance(d.get("message"), str):
        body = error_body(d["code"], d["message"])
    else:
        body = error_body(_CODES.get(exc.status_code, "error" if exc.status_code < 500 else "internal_error"),
                          d if isinstance(d, str) else "request failed")
    return JSONResponse(body, status_code=exc.status_code, headers=getattr(exc, "headers", None))


async def _validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
    parts = ["%s: %s" % (".".join(str(p) for p in e.get("loc", ())), e.get("msg", "invalid")) for e in exc.errors()]
    return JSONResponse(error_body("invalid_request", "; ".join(parts) or "invalid request"), status_code=422)


async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
    """Never leak the exception text (it may carry SQL parameters or uploaded content)."""
    log.exception("unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(error_body("internal_error", "internal error"), status_code=500)


def install(app: FastAPI) -> None:
    app.add_exception_handler(StarletteHTTPException, _http_error)
    app.add_exception_handler(RequestValidationError, _validation_error)
    app.add_exception_handler(Exception, _unhandled)

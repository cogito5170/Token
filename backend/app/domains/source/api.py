"""source.api: the public surface other domains import.

    from app.domains.source.api import open_upload, get_source
    with open_upload(upload_id) as f: ...        # raises HTTPException 404 when missing or purged
"""
from __future__ import annotations

from typing import BinaryIO

from fastapi import HTTPException

from .service import SourceError, SourceRow, UploadRow  # noqa: F401
from .wiring import get_service


def http_error(e: SourceError) -> HTTPException:
    return HTTPException(e.status, detail={"code": e.code, "message": e.message})


def create_upload(ws_id: str, user_id: str, source_id: str, filename: str, file: BinaryIO,
                  declared_format: str | None = None) -> UploadRow:
    try:
        return get_service().create_upload(ws_id, user_id, source_id, filename, file, declared_format)
    except SourceError as e:
        raise http_error(e) from None


def open_upload(upload_id: str) -> BinaryIO:
    try:
        return get_service().open_upload(upload_id)
    except SourceError as e:
        raise http_error(e) from None


def get_source(ws_id: str, source_id: str) -> SourceRow | None:
    return get_service().get_source(ws_id, source_id)

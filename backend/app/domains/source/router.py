"""FastAPI routes: /v1/workspaces/{ws}/sources, /{ws}/uploads. Every {ws} route starts with require_member."""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from pydantic import BaseModel

from app.domains.workspace.api import require_member

from ._identity import current_user
from .api import http_error
from .service import SourceError
from .wiring import get_service, subscribe

router = APIRouter()
subscribe()


class SourceCreate(BaseModel):
    kind: str
    name: str
    project_id: str | None = None


def _s(s):
    return {"id": s.id, "kind": s.kind, "name": s.name, "project_id": s.project_id}


def _u(u):
    return {"id": u.id, "filename": u.filename, "size_bytes": u.size_bytes, "sha256": u.sha256, "job_id": u.job_id}


@router.get("/v1/workspaces/{ws}/sources", tags=["source"])
def list_sources(ws: str, user=Depends(current_user)):
    require_member(ws, user.id)
    return [_s(s) for s in get_service().sources(ws)]


@router.post("/v1/workspaces/{ws}/sources", status_code=201, tags=["source"])
def create_source(ws: str, body: SourceCreate, user=Depends(current_user)):
    require_member(ws, user.id, "developer")
    try:
        return _s(get_service().create_source(ws, body.kind, body.name, body.project_id))
    except SourceError as e:
        raise http_error(e) from None


@router.post("/v1/workspaces/{ws}/uploads", status_code=201, tags=["source"])
def create_upload(ws: str, request: Request, source_id: str = Form(...), file: UploadFile = File(...),
                  declared_format: str | None = Form(None), user=Depends(current_user)):
    require_member(ws, user.id, "developer")
    try:
        cl = request.headers.get("content-length")
        return _u(get_service().create_upload(ws, user.id, source_id, file.filename or "", file.file,
                                              declared_format or None,
                                              int(cl) - 65536 if cl and cl.isdigit() else None))  # multipart overhead slack
    except SourceError as e:
        raise http_error(e) from None

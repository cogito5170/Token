"""FastAPI routes: /v1/workspaces/{ws}/reports, /reports/{report}/export. Read = member; generate = developer+;
non-member 404."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response

from app.domains.identity.api import current_user
from app.domains.workspace.api import require_member

from .service import ReportError
from .wiring import get_service

router = APIRouter()


def _run(fn, *a, **k):
    try:
        return fn(*a, **k)
    except ReportError as e:
        raise HTTPException(e.status, detail={"code": e.code, "message": e.message}) from None


@router.get("/v1/workspaces/{ws}/reports", tags=["report"])
def list_reports(ws: str, user=Depends(current_user)):
    require_member(ws, user.id)
    svc = get_service()
    return [svc.view(r) for r in svc.list(ws)]


@router.post("/v1/workspaces/{ws}/reports", tags=["report"], status_code=201)
def generate_report(ws: str, body: dict, user=Depends(current_user)):
    require_member(ws, user.id, "developer")
    svc = get_service()
    return svc.view(_run(svc.generate, ws, body, user.id))


@router.get("/v1/workspaces/{ws}/reports/{report}/export", tags=["report"])
def export_report(ws: str, report: str, format: str = Query(...), user=Depends(current_user)):
    require_member(ws, user.id)
    ctype, text = _run(get_service().export, ws, report, format, user.id)
    return Response(text, media_type=ctype)

"""FastAPI routes: /v1/workspaces/{ws}/estimates, /estimates/{estimate}, /estimation/accuracy.
Read = member; create = developer+; non-member 404. A malformed estimate id is a 404, not a database error."""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Body, Depends, HTTPException, Query

from app.domains.identity.api import current_user
from app.domains.workspace.api import require_member

from .api import get_service
from .service import EstimationError, valid_uuid

router = APIRouter()


def _run(fn, *a, **k):
    try:
        return fn(*a, **k)
    except EstimationError as e:
        raise HTTPException(e.status, detail={"code": e.code, "message": e.message}) from None


@router.get("/v1/workspaces/{ws}/estimates", tags=["estimation"])
def list_estimates(ws: str, user=Depends(current_user)):
    require_member(ws, user.id)
    svc = get_service()
    return [svc.view(r) for r in svc.list(ws)]


@router.post("/v1/workspaces/{ws}/estimates", tags=["estimation"], status_code=201)
def create_estimate(ws: str, body: dict = Body(...), user=Depends(current_user)):
    require_member(ws, user.id, "developer")
    svc = get_service()
    return svc.view(_run(svc.create, ws, body, user.id))


@router.get("/v1/workspaces/{ws}/estimates/{estimate}", tags=["estimation"])
def get_estimate(ws: str, estimate: str, user=Depends(current_user)):
    require_member(ws, user.id)
    svc = get_service()
    row = svc.get(ws, estimate) if valid_uuid(estimate) else None
    if row is None:
        raise HTTPException(404, detail={"code": "not_found", "message": "estimate not found"})
    return svc.view(row)


@router.get("/v1/workspaces/{ws}/estimation/accuracy", tags=["estimation"])
def estimate_accuracy(ws: str, user=Depends(current_user), frm: datetime | None = Query(None, alias="from"),
                      to: datetime | None = Query(None)):
    require_member(ws, user.id)
    return get_service().accuracy_view(ws, frm, to)

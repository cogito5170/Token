"""FastAPI routes: /v1/workspaces/{ws}/profile*. Every route starts with require_member and acts on the caller only."""
from __future__ import annotations

from fastapi import APIRouter, Body, Depends, HTTPException

from app.domains.workspace.api import require_member

from ._identity import current_user
from .service import ProfileError
from .wiring import get_service, subscribe

router = APIRouter()
subscribe()


def _run(fn, *a):
    try:
        return fn(*a)
    except ProfileError as e:
        raise HTTPException(e.status, detail={"code": e.code, "message": e.message}) from None


@router.get("/v1/workspaces/{ws}/profile", tags=["profile"])
def get_profile(ws: str, user=Depends(current_user)):
    require_member(ws, user.id)
    return _run(get_service().get_profile, ws, user.id)


@router.put("/v1/workspaces/{ws}/profile", tags=["profile"])
def put_profile(ws: str, body: dict = Body(...), user=Depends(current_user)):
    require_member(ws, user.id)
    return _run(get_service().put_profile, ws, user.id, body)


@router.get("/v1/workspaces/{ws}/profile/stats", tags=["profile"])
def get_stats(ws: str, user=Depends(current_user)):
    require_member(ws, user.id)
    return _run(get_service().stats, ws, user.id)


@router.get("/v1/workspaces/{ws}/profile/recommendations", tags=["profile"])
def list_recommendations(ws: str, user=Depends(current_user)):
    require_member(ws, user.id)
    return _run(get_service().recommendations, ws, user.id)

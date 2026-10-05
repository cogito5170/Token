"""FastAPI routes: /v1/workspaces/{ws}/simulations*. Every route starts with require_member."""
from __future__ import annotations

from fastapi import APIRouter, Body, Depends, HTTPException

from app.domains.workspace.api import require_member

from ._identity import current_user
from .service import SimulationError
from .wiring import get_service

router = APIRouter()


def _run(fn, *a):
    try:
        return fn(*a)
    except SimulationError as e:
        raise HTTPException(e.status, detail={"code": e.code, "message": e.message}) from None


@router.post("/v1/workspaces/{ws}/simulations", status_code=201, tags=["simulation"])
def create_simulation(ws: str, body: dict = Body(...), user=Depends(current_user)):
    require_member(ws, user.id)
    return _run(get_service().simulate, ws, user.id, body.get("assumptions"), body.get("basis"))


@router.get("/v1/workspaces/{ws}/simulations/{simulation}", tags=["simulation"])
def get_simulation(ws: str, simulation: str, user=Depends(current_user)):
    require_member(ws, user.id)
    return _run(get_service().get, ws, simulation)

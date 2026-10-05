"""FastAPI routes: /v1/workspaces/{ws}/budgets*, /quota/alerts. Read = member; write = admin; non-member 404."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field

from app.domains.identity.api import current_user
from app.domains.workspace.api import require_member

from .service import QuotaError
from .wiring import get_service

router = APIRouter()


class BudgetCreate(BaseModel):
    scope: str
    period: str
    measure: str
    limit_microusd: int = Field(ge=1)
    project_id: str | None = None
    thresholds: list[int] | None = None
    action_at_limit: str = "alert"


def _run(fn, *a, **k):
    try:
        return fn(*a, **k)
    except QuotaError as e:
        raise HTTPException(e.status, detail={"code": e.code, "message": e.message}) from None


@router.get("/v1/workspaces/{ws}/budgets", tags=["quota"])
def list_budgets(ws: str, user=Depends(current_user)):
    require_member(ws, user.id)
    return _run(get_service().list, ws)


@router.post("/v1/workspaces/{ws}/budgets", tags=["quota"], status_code=201)
def create_budget(ws: str, body: BudgetCreate, user=Depends(current_user)):
    require_member(ws, user.id, "admin")
    svc = get_service()
    b = _run(svc.create, ws, user.id, body.scope, body.period, body.measure, body.limit_microusd, body.project_id,
             body.thresholds, body.action_at_limit)
    return svc.view(b)


@router.get("/v1/workspaces/{ws}/budgets/{budget}", tags=["quota"])
def get_budget(ws: str, budget: str, user=Depends(current_user)):
    require_member(ws, user.id)
    svc = get_service()
    return svc.view(_run(svc.get, ws, budget))


@router.delete("/v1/workspaces/{ws}/budgets/{budget}", tags=["quota"], status_code=204)
def archive_budget(ws: str, budget: str, user=Depends(current_user)):
    require_member(ws, user.id, "admin")
    _run(get_service().archive, ws, budget, user.id)
    return Response(status_code=204)


@router.get("/v1/workspaces/{ws}/budgets/{budget}/burn", tags=["quota"])
def budget_burn(ws: str, budget: str, user=Depends(current_user)):
    require_member(ws, user.id)
    return _run(get_service().burn, ws, budget)


@router.get("/v1/workspaces/{ws}/quota/alerts", tags=["quota"])
def list_alerts(ws: str, user=Depends(current_user)):
    require_member(ws, user.id)
    return get_service().alerts(ws)

"""FastAPI routes: /v1/models and /v1/workspaces/{ws}/usage/*. Every {ws} route starts with require_member."""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.domains.workspace.api import require_member

from ._identity import current_user
from .service import UsageError
from .wiring import get_service

router = APIRouter()


def _err(e: UsageError) -> HTTPException:
    return HTTPException(e.status, detail={"code": e.code, "message": e.message})


class TaskUpdate(BaseModel):
    kind: str | None = None
    outcome: str | None = None
    structure: str | None = None
    context_mode: str | None = None


def _run(fn, *a, **kw):
    try:
        return fn(*a, **kw)
    except UsageError as e:
        raise _err(e) from None


@router.get("/v1/models", tags=["usage"])
def list_models(user=Depends(current_user)):
    return get_service().list_models()


@router.get("/v1/workspaces/{ws}/usage/summary", tags=["usage"])
def usage_summary(ws: str, from_: datetime | None = Query(None, alias="from"), to: datetime | None = None,
                  project: str | None = None, user=Depends(current_user)):
    require_member(ws, user.id)
    return _run(get_service().summary, ws, from_, to, project)


@router.get("/v1/workspaces/{ws}/usage/series/tokens", tags=["usage"])
def token_series(ws: str, from_: datetime | None = Query(None, alias="from"), to: datetime | None = None,
                 project: str | None = None, bucket: str = "day", group_by: str = "none", user=Depends(current_user)):
    require_member(ws, user.id)
    return _run(get_service().token_series, ws, from_, to, project, bucket, group_by)


@router.get("/v1/workspaces/{ws}/usage/series/call-size", tags=["usage"])
def call_size(ws: str, from_: datetime | None = Query(None, alias="from"), to: datetime | None = None,
              project: str | None = None, threshold: int = 50000, user=Depends(current_user)):
    require_member(ws, user.id)
    return _run(get_service().call_size, ws, from_, to, project, threshold)


@router.get("/v1/workspaces/{ws}/usage/compare", tags=["usage"])
def compare(ws: str, dims: str, from_: datetime | None = Query(None, alias="from"), to: datetime | None = None,
            project: str | None = None, user=Depends(current_user)):
    require_member(ws, user.id)
    return _run(get_service().compare, ws, [d for d in dims.split(",") if d], from_, to, project)


@router.get("/v1/workspaces/{ws}/usage/calls", tags=["usage"])
def list_calls(ws: str, from_: datetime | None = Query(None, alias="from"), to: datetime | None = None,
               project: str | None = None, cursor: str | None = None, min_input: int | None = None,
               model: str | None = None, user=Depends(current_user)):
    require_member(ws, user.id)
    return _run(get_service().call_page, ws, from_, to, project, cursor, 100, min_input, model)


@router.get("/v1/workspaces/{ws}/usage/sessions", tags=["usage"])
def list_sessions(ws: str, from_: datetime | None = Query(None, alias="from"), to: datetime | None = None,
                  cursor: str | None = None, user=Depends(current_user)):
    require_member(ws, user.id)
    return _run(get_service().session_page, ws, from_, to, cursor)


@router.get("/v1/workspaces/{ws}/usage/tasks", tags=["usage"])
def list_tasks(ws: str, from_: datetime | None = Query(None, alias="from"), to: datetime | None = None,
               cursor: str | None = None, user=Depends(current_user)):
    require_member(ws, user.id)
    return _run(get_service().task_page, ws, from_, to, cursor)


@router.patch("/v1/workspaces/{ws}/usage/tasks/{task}", tags=["usage"])
def update_task(ws: str, task: str, body: TaskUpdate, user=Depends(current_user)):
    require_member(ws, user.id, "developer")
    return _run(get_service().update_task, ws, user.id, task, body.kind, body.outcome, body.structure,
                body.context_mode)

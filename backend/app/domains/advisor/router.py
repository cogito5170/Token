"""FastAPI routes: /v1/workspaces/{ws}/advisor/{rules,findings}, /proposals*. Read = member; decide = developer+ (the
service applies the per-kind policy on top); non-member 404."""
from __future__ import annotations

from datetime import date, datetime, time, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.domains.identity.api import current_user
from app.domains.workspace.api import require_member

from .service import AdvisorError
from .wiring import get_service

router = APIRouter()


class Decision(BaseModel):
    decision: str
    confirm: bool = False
    note: str = ""


def _run(fn, *a, **k):
    try:
        return fn(*a, **k)
    except AdvisorError as e:
        raise HTTPException(e.status, detail={"code": e.code, "message": e.message}) from None


def _day(d: date | None, end: bool = False) -> datetime | None:
    return None if d is None else datetime.combine(d, time.max if end else time.min, tzinfo=timezone.utc)


def view(svc, p) -> dict:
    return {"id": p.id, "origin": p.origin, "origin_ref": p.origin_ref, "kind": p.kind, "change": p.change,
            "expected_savings": {"value": p.expected_savings_microusd, "unit": "microusd", "provenance": "ESTIMATED"},
            "state": p.state, "blocked_reason": p.blocked_reason,
            "decisions": [{"decision": d.decision, "decided_by": d.decided_by, "decided_at": d.decided_at.isoformat(),
                           "policy_ok": d.policy_ok, "budget_ok": d.budget_ok} for d in svc.decisions(p.id)]}


@router.get("/v1/workspaces/{ws}/advisor/rules", tags=["advisor"])
def list_rules(ws: str, user=Depends(current_user)):
    require_member(ws, user.id)
    return get_service().list_rules(ws)


@router.get("/v1/workspaces/{ws}/advisor/findings", tags=["advisor"])
def list_findings(ws: str, from_: date | None = Query(None, alias="from"), to: date | None = None, user=Depends(current_user)):
    require_member(ws, user.id)
    return get_service().list_findings(ws, _day(from_), _day(to, True))


@router.get("/v1/workspaces/{ws}/proposals", tags=["advisor"])
def list_proposals(ws: str, state: str | None = None, user=Depends(current_user)):
    require_member(ws, user.id)
    svc = get_service()
    return [view(svc, p) for p in _run(svc.list_proposals, ws, state)]


@router.get("/v1/workspaces/{ws}/proposals/{proposal}", tags=["advisor"])
def get_proposal(ws: str, proposal: str, user=Depends(current_user)):
    require_member(ws, user.id)
    svc = get_service()
    return view(svc, _run(svc.get_proposal, ws, proposal))


@router.post("/v1/workspaces/{ws}/proposals/{proposal}/decision", tags=["advisor"])
def decide_proposal(ws: str, proposal: str, body: Decision, user=Depends(current_user)):
    m = require_member(ws, user.id, "developer")
    svc = get_service()
    return view(svc, _run(svc.decide, ws, user.id, m.role, proposal, body.decision, body.confirm, body.note))

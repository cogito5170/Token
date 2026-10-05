"""FastAPI route: GET /v1/workspaces/{ws}/audit-log (admin only; non-member 404, non-admin 403)."""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query

from app.domains.identity.api import current_user
from app.domains.workspace.api import require_member

from .service import AuditError
from .wiring import get_service

router = APIRouter()


def _e(r) -> dict:
    return {"id": r.id, "at": r.at.isoformat(), "actor_user_id": r.actor_user_id, "actor_kind": r.actor_kind,
            "action": r.action, "target_kind": r.target_kind, "target_id": r.target_id, "detail": r.detail}


@router.get("/v1/workspaces/{ws}/audit-log", tags=["audit"])
def list_audit_log(ws: str, action: str | None = None, from_: datetime | None = Query(default=None, alias="from"),
                   to: datetime | None = None, cursor: str | None = None, limit: int = 50, user=Depends(current_user)):
    m = require_member(ws, user.id)  # 404 for non-members
    try:
        rows, nxt = get_service().query(ws, m.role, action=action, frm=from_, to=to, cursor=cursor, limit=limit)
    except AuditError as e:
        raise HTTPException(e.status, detail={"code": e.code, "message": e.message}) from None
    return {"items": [_e(r) for r in rows], "next_cursor": nxt}

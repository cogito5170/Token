"""workspace.api: the public surface other domains import (`require_member`).

    from app.domains.workspace.api import require_member
    m = require_member(ws, user.id, "developer")   # raises HTTPException 404 (non-member) / 403 (role too low)
"""
from __future__ import annotations

from fastapi import HTTPException

from .service import RANK, ROLES, MemberRow, WorkspaceError, WorkspaceService  # noqa: F401
from .wiring import get_service


def http_error(e: WorkspaceError) -> HTTPException:
    return HTTPException(e.status, detail={"code": e.code, "message": e.message})


def require_member(ws: str, user_id: str, min_role: str = "viewer") -> MemberRow:
    try:
        return get_service().require_member(ws, user_id, min_role)
    except WorkspaceError as e:
        raise http_error(e) from None

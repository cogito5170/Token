"""audit.api: the public surface other domains import (`record`).

    from app.domains.audit.api import record
    record("proposal.apply", user.id, {"workspace_id": ws, "proposal_id": pid})

Shape (action, actor, detail) is what identity/workspace take as their injected recorder, so
`set_audit_recorder(audit.api.record)` needs no adapter. Raises AuditError (422) when detail could hold a secret.
"""
from __future__ import annotations

from .service import AuditError, AuditRow, AuditService  # noqa: F401
from .wiring import get_service


def record(action: str, actor: str | None, detail: dict | None = None, *, workspace_id: str | None = None,
           target_kind: str | None = None, target_id: str | None = None, actor_kind: str | None = None,
           request_id: str | None = None) -> AuditRow:
    return get_service().record(action, actor, detail, workspace_id=workspace_id, target_kind=target_kind,
                                target_id=target_id, actor_kind=actor_kind, request_id=request_id)


def query(ws: str, role: str, **filters):
    return get_service().query(ws, role, **filters)

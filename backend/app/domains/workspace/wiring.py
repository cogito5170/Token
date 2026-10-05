"""Service singleton and event subscription (kept apart from api/router to avoid import cycles)."""
from __future__ import annotations

from app.core import events

from .service import WorkspaceService

_service: WorkspaceService | None = None
_audit = None
_subscribed = False


def set_audit_recorder(fn) -> None:
    """Swap the audit recorder (tests inject a fake); the default is audit.api.record."""
    global _audit, _service
    _audit, _service = fn, None


def get_service() -> WorkspaceService:
    global _service
    if _service is None:
        from app.core.db import get_pool

        from app.domains.audit.api import record as audit_record

        from .pg_store import PgStore

        kw = {"audit": _audit or audit_record}
        _service = WorkspaceService(PgStore(get_pool()), **kw)
    return _service


def _on_user_created(name: str, payload: dict) -> None:
    get_service().on_user_created(name, payload)


def subscribe(bus=events.bus) -> None:
    global _subscribed
    if not _subscribed:
        bus.subscribe("identity.user.created", _on_user_created)
        _subscribed = True

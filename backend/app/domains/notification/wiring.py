"""Service singleton and event subscription (kept apart from api/router to avoid import cycles)."""
from __future__ import annotations

import weakref

from .service import EVENT_KINDS, NotificationService

_service: NotificationService | None = None
_member_lookup = None
_subscribed = weakref.WeakSet()  # buses that already carry the handlers


def set_member_lookup(fn) -> None:
    """Override how a workspace id maps to its member user ids (tests, or until workspace.api offers one)."""
    global _member_lookup
    _member_lookup = fn


def _workspace_members(ws: str) -> list[str]:
    """workspace.api.member_ids(ws) when that domain offers it; otherwise no workspace fan-out (user_id targets still work)."""
    if _member_lookup is not None:
        return list(_member_lookup(ws))
    from app.domains.workspace import api as workspace_api

    fn = getattr(workspace_api, "member_ids", None)
    return list(fn(ws)) if fn else []


def get_service() -> NotificationService:
    global _service
    if _service is None:
        from app.core.db import get_pool

        from .pg_store import PgStore

        _service = NotificationService(PgStore(get_pool()), _workspace_members)
    return _service


def subscribe(bus, service: NotificationService | None = None) -> None:
    """Subscribe one handler per event kind. The service is resolved at event time unless one is given.

    Idempotent per bus (the router import and the process assembly both call it; a second set would notify twice)."""
    if service is None:
        if bus in _subscribed:
            return
        _subscribed.add(bus)
    for name in EVENT_KINDS:
        bus.subscribe(name, lambda n, p: (service or get_service()).on_event(n, p))

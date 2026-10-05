"""Service singleton (kept apart from api/router to avoid import cycles)."""
from __future__ import annotations

from .service import UsageService

_service: UsageService | None = None


def get_service() -> UsageService:
    global _service
    if _service is None:
        from app.core import events
        from app.core.db import get_pool

        from .pg_store import PgStore, seed

        pool = get_pool()
        seed(pool)
        _service = UsageService(PgStore(pool), publish=events.bus.publish)
    return _service


def set_service(svc: UsageService | None) -> None:
    """Test hook / alternative wiring."""
    global _service
    _service = svc

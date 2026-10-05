"""Service singleton (kept apart from api/router to avoid import cycles)."""
from __future__ import annotations

from .service import AuditService

_service: AuditService | None = None


def get_service() -> AuditService:
    global _service
    if _service is None:
        from app.core.db import get_pool

        from .pg_store import PgStore

        _service = AuditService(PgStore(get_pool()))
    return _service

"""Service singleton (kept apart from api/router to avoid import cycles)."""
from __future__ import annotations

from .service import QuotaService

_service: QuotaService | None = None


def set_service(svc: QuotaService | None) -> None:
    global _service
    _service = svc


def get_service() -> QuotaService:
    global _service
    if _service is None:
        from app.core.db import get_pool
        from app.domains.audit.api import record
        from app.domains.usage.api import summary

        from .pg_store import PgStore

        _service = QuotaService(PgStore(get_pool()), summary, audit=record)
    return _service

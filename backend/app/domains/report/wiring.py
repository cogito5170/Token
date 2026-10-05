"""Service singleton (kept apart from api/router to avoid import cycles)."""
from __future__ import annotations

from .service import ReportService

_service: ReportService | None = None


def set_service(svc: ReportService | None) -> None:
    global _service
    _service = svc


def get_service() -> ReportService:
    global _service
    if _service is None:
        from app.core import events
        from app.core.db import get_pool
        from app.domains.advisor.api import list_findings
        from app.domains.audit.api import record
        from app.domains.quota import api as quota
        from app.domains.usage.api import summary

        from .pg_store import PgStore

        # quota.api exposes no budget list yet (request to baseline): without one the budget section is empty.
        budgets = getattr(quota, "list_budgets", lambda ws: [])
        _service = ReportService(PgStore(get_pool()), summary, list_findings, budgets, quota.burn, audit=record,
                                 publish=events.bus.publish)
    return _service

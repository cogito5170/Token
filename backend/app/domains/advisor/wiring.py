"""Service singleton and event subscription (kept apart from api/router to avoid import cycles)."""
from __future__ import annotations

from app.core import events

from .service import AdvisorService

_service: AdvisorService | None = None
_subscribed = False


def set_service(svc: AdvisorService | None) -> None:
    global _service
    _service = svc


def get_service() -> AdvisorService:
    global _service
    if _service is None:
        from app.core.db import get_pool
        from app.domains.audit.api import record
        from app.domains.quota.api import check
        from app.domains.usage import api as usage

        from .pg_store import PgStore

        # usage.api exposes no price table yet (request to baseline): without one R3-R5 cannot price a tier.
        prices = getattr(usage, "prices", lambda: {})
        _service = AdvisorService(PgStore(get_pool()), usage.calls, usage.tasks, prices, check, record,
                                  publish=events.bus.publish)
    return _service


def _on_ingested(name: str, payload: dict) -> None:
    get_service().on_calls_ingested(name, payload)


def subscribe(bus=events.bus) -> None:
    global _subscribed
    if not _subscribed:
        bus.subscribe("usage.calls.ingested", _on_ingested)
        _subscribed = True

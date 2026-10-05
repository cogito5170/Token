"""Service singleton, usage-event subscription and the two cross-domain seams (kept apart from api/router)."""
from __future__ import annotations

import importlib

from app.core import events

from .service import ProfileService

_service: ProfileService | None = None
_subscribed = False


def _usage_tasks(ws: str) -> list[dict]:
    from app.domains.usage import api as usage

    out, cursor = [], None
    while True:
        page = usage.tasks(ws, cursor=cursor, limit=500)
        out.extend(page["items"])
        cursor = page.get("next_cursor")
        if not cursor:
            return out


def _advisor_proposer():
    """advisor.api.submit_proposal once it lands (CMD-GC30); None until then (to_proposal answers 503)."""
    try:
        return importlib.import_module("app.domains.advisor.api").submit_proposal
    except (ModuleNotFoundError, AttributeError):
        return None


def get_service() -> ProfileService:
    global _service
    if _service is None:
        from app.core.db import get_pool

        from .pg_store import PgStore

        _service = ProfileService(PgStore(get_pool()), _usage_tasks, _advisor_proposer(), events.bus.publish)
    return _service


def set_service(svc: ProfileService | None) -> None:
    """Test hook / alternative wiring."""
    global _service
    _service = svc


def _on_usage(name: str, payload: dict) -> None:
    get_service().on_usage_ingested(name, payload)


def subscribe(bus=events.bus) -> None:
    global _subscribed
    if not _subscribed:
        bus.subscribe("usage.calls.ingested", _on_usage)
        bus.subscribe("usage.task.outcome_set", _on_usage)
        _subscribed = True

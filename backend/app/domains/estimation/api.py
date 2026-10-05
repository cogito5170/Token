"""estimation.api: public surface for other domains."""
from __future__ import annotations

from .service import EstimationError, EstimationService  # noqa: F401

_service: EstimationService | None = None


def set_service(svc: EstimationService | None) -> None:
    global _service
    _service = svc


def _usage_tasks(ws: str) -> list[dict]:
    from app.domains.usage import api as usage

    out, cursor = [], None
    while True:
        page = usage.tasks(ws, cursor=cursor, limit=500)
        out.extend(page.get("items", []))
        cursor = page.get("next_cursor")
        if not cursor:
            return out


def get_service() -> EstimationService:
    global _service
    if _service is None:
        from app.core.db import get_pool

        from .pg_store import PgStore

        _service = EstimationService(_usage_tasks, store=PgStore(get_pool()))
    return _service


def create_estimate(ws: str, request: dict, user_id: str | None = None) -> dict:
    return get_service().create(ws, request, user_id)


def record_outcome(estimate_id: str, actual: dict, ws: str | None = None, task_id: str | None = None) -> dict:
    return get_service().record_outcome(estimate_id, actual, ws, task_id)


def accuracy(quantity: str = "total_tokens", ws: str | None = None) -> dict:
    return get_service().accuracy(quantity, ws)

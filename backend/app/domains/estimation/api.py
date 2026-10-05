"""estimation.api: public surface for other domains."""
from __future__ import annotations

from .service import EstimationError, EstimationService  # noqa: F401

_service: EstimationService | None = None


def get_service() -> EstimationService:
    global _service
    if _service is None:
        from app.domains.usage import api as usage

        def tasks_fn(ws):
            return usage.tasks(ws, limit=1000).get("items", [])

        _service = EstimationService(tasks_fn)
    return _service


def create_estimate(ws: str, request: dict) -> dict:
    return get_service().create(ws, request)


def record_outcome(estimate_id: str, actual: dict) -> dict:
    return get_service().record_outcome(estimate_id, actual)


def accuracy(quantity: str = "total_tokens") -> dict:
    return get_service().accuracy(quantity)

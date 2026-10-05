"""quota.api: the public surface other domains import.

    from app.domains.quota.api import check
    check(ws, "workspace", extra_cost_microusd)  # -> {"allowed": bool, "blocked_by": [...]}
"""
from __future__ import annotations

from .service import Budget, QuotaError, QuotaService  # noqa: F401
from .wiring import get_service


def check(ws, scope, extra_cost, project_id=None, cost_cli=None) -> dict:
    return get_service().check(ws, scope, extra_cost, project_id, cost_cli)


def burn(ws, budget_id) -> dict:
    return get_service().burn(ws, budget_id)


def evaluate(ws):
    return get_service().evaluate(ws)

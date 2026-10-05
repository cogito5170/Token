"""Service singleton and the cross-domain seams (usage.api, profile.api, advisor.api), kept apart from api/router."""
from __future__ import annotations

import importlib

from app.core import events

from .service import SimulationService

_service: SimulationService | None = None


def _paged(fn, ws, *args):
    out, cursor = [], None
    while True:
        page = fn(ws, *args, cursor=cursor, limit=500)
        out.extend(page["items"])
        cursor = page.get("next_cursor")
        if not cursor:
            return out


def _calls(ws, t_from, t_to, project):
    from app.domains.usage import api as usage
    return _paged(usage.calls, ws, t_from, t_to, project)


def _tasks(ws, t_from, t_to):
    from app.domains.usage import api as usage
    return _paged(usage.tasks, ws, t_from, t_to)


def _stats(ws, user):
    from app.domains.profile import api as profile
    return profile.stats(ws, user)


def _prices():
    """usage.api.prices() -> {model: {"version", "in", "out", "cr", "cw5"}} (micro-USD per Mtok). usage.api does not
    export it yet (request to baseline); until then this answers {} and simulate() answers 503."""
    try:
        return importlib.import_module("app.domains.usage.api").prices()
    except (ModuleNotFoundError, AttributeError):
        return {}


def _advisor_proposer():
    """advisor.api.submit_proposal once it lands (CMD-GC30); None until then (to_proposal answers 503)."""
    try:
        return importlib.import_module("app.domains.advisor.api").submit_proposal
    except (ModuleNotFoundError, AttributeError):
        return None


def get_service() -> SimulationService:
    global _service
    if _service is None:
        from app.core.db import get_pool

        from .store import PgStore

        _service = SimulationService(PgStore(get_pool()), _calls, _tasks, _stats, _prices, _advisor_proposer(),
                                     events.bus.publish)
    return _service


def set_service(svc: SimulationService | None) -> None:
    """Test hook / alternative wiring."""
    global _service
    _service = svc

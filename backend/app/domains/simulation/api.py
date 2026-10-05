"""simulation.api: the public surface other domains import.

    from app.domains.simulation.api import simulate, get, to_proposal
"""
from __future__ import annotations

from .service import SimulationError, SimulationService  # noqa: F401
from .wiring import get_service


def simulate(ws, user, assumptions, basis) -> dict:
    return get_service().simulate(ws, user, assumptions, basis)


def get(ws, sim_id) -> dict:
    return get_service().get(ws, sim_id)


def to_proposal(ws, sim_id) -> dict:
    return get_service().to_proposal(ws, sim_id)

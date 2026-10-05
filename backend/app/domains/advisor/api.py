"""advisor.api: the public surface other domains import.

    from app.domains.advisor.api import submit_proposal, list_findings
    submit_proposal(ws, "simulation", sim_id, "context_cap", {...}, expected_savings=1200)  # -> ProposalRow
"""
from __future__ import annotations

from .service import AdvisorError, FindingRow, ProposalRow  # noqa: F401
from .wiring import get_service


def run_rules(ws, t_from=None, t_to=None):
    return get_service().run_rules(ws, t_from, t_to)


def submit_proposal(ws, origin, origin_ref, kind, change, expected_savings=None, actor=None):
    return get_service().submit_proposal(ws, origin, origin_ref, kind, change, expected_savings, actor)


def list_findings(ws, t_from=None, t_to=None) -> list[dict]:
    return get_service().list_findings(ws, t_from, t_to)


def decide(ws, user, role, proposal_id, decision, confirm=False, note=""):
    return get_service().decide(ws, user, role, proposal_id, decision, confirm, note)

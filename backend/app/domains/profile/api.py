"""profile.api: the public surface other domains import (simulation reads stats; report reads the profile).

    from app.domains.profile.api import get_profile, stats, refresh_stats, recommendations, to_proposal
"""
from __future__ import annotations

from .service import ProfileError, ProfileService, Stat, compute_stats, recommend  # noqa: F401
from .wiring import get_service


def get_profile(ws, user) -> dict:
    return get_service().get_profile(ws, user)


def stats(ws, user) -> list[dict]:
    return get_service().stats(ws, user)


def refresh_stats(ws, users=None) -> int:
    return get_service().refresh_stats(ws, users)


def recommendations(ws, user) -> list[dict]:
    return get_service().recommendations(ws, user)


def to_proposal(ws, user, rec_id) -> dict:
    return get_service().to_proposal(ws, user, rec_id)

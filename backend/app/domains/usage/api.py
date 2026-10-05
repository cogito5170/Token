"""usage.api: the public surface other domains import.

    from app.domains.usage.api import load_calls, CallIn, tasks, calls
    load_calls(ws, project_id, source_id, job_id, [CallIn(...)], sessions={...}, tasks={...})  # -> LoadResult

Reads return the same JSON-shaped dicts as the HTTP routes (cost fields in micro-USD integers; null = unknown).
"""
from __future__ import annotations

from .service import CallIn, LoadResult, SessionIn, TaskIn, UsageError, UsageService  # noqa: F401
from .wiring import get_service


def load_calls(ws, project_id, source_id, ingest_job_id, calls, sessions=None, tasks=None) -> LoadResult:
    return get_service().load_calls(ws, project_id, source_id, ingest_job_id, calls, sessions, tasks)


def summary(ws, t_from=None, t_to=None, project=None) -> dict:
    return get_service().summary(ws, t_from, t_to, project)


def calls(ws, t_from=None, t_to=None, project=None, cursor=None, limit=100, min_input=None, model=None) -> dict:
    return get_service().call_page(ws, t_from, t_to, project, cursor, limit, min_input, model)


def tasks(ws, t_from=None, t_to=None, cursor=None, limit=100) -> dict:
    return get_service().task_page(ws, t_from, t_to, cursor, limit)

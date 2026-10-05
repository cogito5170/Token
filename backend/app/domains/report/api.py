"""report.api: the public surface other domains import.

    from app.domains.report.api import generate, export
    row = generate(ws, {"from": "2026-10-01", "to": "2026-10-31"})
    content_type, text = export(ws, row.id, "csv")
"""
from __future__ import annotations

from .service import ReportError, ReportRow  # noqa: F401
from .wiring import get_service


def generate(ws, period, actor=None) -> ReportRow:
    return get_service().generate(ws, period, actor)


def export(ws, report_id, fmt, actor=None) -> tuple[str, str]:
    return get_service().export(ws, report_id, fmt, actor)

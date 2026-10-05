"""ingestion.api: the public surface other domains import.

    from app.domains.ingestion.api import enqueue
    job_id = enqueue(upload_id)        # the hook for source: Upload.job_id; idempotent per live upload

App assembly wires it with `source.wiring.set_enqueuer(ingestion.api.enqueue)` (request to baseline, see report).
"""
from __future__ import annotations

from .service import IngestError, IngestService  # noqa: F401
from .wiring import get_service


def enqueue(upload_id: str) -> str:
    return get_service().enqueue(upload_id)

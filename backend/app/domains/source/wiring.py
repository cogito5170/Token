"""Service singleton and event subscription (kept apart from api/router to avoid import cycles)."""
from __future__ import annotations

from app.core import events

from .service import FileObjectStore, SourceService

_service: SourceService | None = None
_enqueue = None
_subscribed = False


def set_enqueuer(fn) -> None:
    """Wire ingestion's enqueue(upload_id) -> job_id here once it lands, so POST /uploads returns job_id."""
    global _enqueue, _service
    _enqueue, _service = fn, None


def get_service() -> SourceService:
    global _service
    if _service is None:
        from app.core.config import load_settings
        from app.core.db import get_pool

        from .pg_store import PgStore

        s = load_settings()
        _service = SourceService(PgStore(get_pool()), FileObjectStore(s.upload_dir), s.upload_max_bytes,
                                 publish=events.bus.publish, enqueue=_enqueue)
    return _service


def _on_job_finished(name: str, payload: dict) -> None:
    get_service().on_job_finished(name, payload)


def subscribe(bus=events.bus) -> None:
    global _subscribed
    if not _subscribed:
        bus.subscribe("ingestion.job.finished", _on_job_finished)
        _subscribed = True

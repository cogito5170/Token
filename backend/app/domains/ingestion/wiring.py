"""Service singleton (kept apart from api/router to avoid import cycles)."""
from __future__ import annotations

from .service import IngestService

_service: IngestService | None = None


def get_service() -> IngestService:
    global _service
    if _service is None:
        from app.core import events
        from app.core.db import get_pool
        from app.domains.source.api import get_source, open_upload
        from app.domains.usage.api import load_calls

        from .pg_store import PgStore

        _service = IngestService(PgStore(get_pool()), open_upload, load_calls, get_source, publish=events.bus.publish)
    return _service


def set_service(svc: IngestService | None) -> None:
    """Test hook / alternative wiring."""
    global _service
    _service = svc

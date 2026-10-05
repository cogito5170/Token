"""Service singleton (kept apart from api/router to avoid import cycles)."""
from __future__ import annotations

from app.core import events

from .crypto import EnvKeyring
from .service import IntegrationService

_service: IntegrationService | None = None
_audit = None


def set_audit_recorder(fn) -> None:
    """Swap the audit recorder (tests inject a fake); the default is audit.api.record."""
    global _audit, _service
    _audit, _service = fn, None


def get_service() -> IntegrationService:
    global _service
    if _service is None:
        from app.core.db import get_pool

        from app.domains.audit.api import record as audit_record

        from .pg_store import PgStore

        _service = IntegrationService(PgStore(get_pool()), EnvKeyring(), audit=_audit or audit_record,
                                      publish=events.bus.publish)
    return _service

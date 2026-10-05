"""Process assembly: which domain hooks and event subscribers each process installs (CMD-GC19).

`wire_api()` runs in create_app(), `wire_worker()` in `python -m app.worker`. Both are idempotent. The event bus is
in-process, so a subscriber only hears events published in its own process; app/worker/README.md says which events
are produced where.
"""
from __future__ import annotations

from app.core import events


def wire_api(bus=events.bus) -> None:
    from app.domains.advisor import wiring as advisor
    from app.domains.audit import api as audit
    from app.domains.identity import router as identity
    from app.domains.ingestion import api as ingestion
    from app.domains.notification import wiring as notification
    from app.domains.profile import wiring as profile
    from app.domains.source import wiring as source
    from app.domains.workspace import wiring as workspace

    identity.set_audit_recorder(audit.record)
    workspace.set_audit_recorder(audit.record)
    workspace.subscribe(bus)
    source.set_enqueuer(ingestion.enqueue)
    source.subscribe(bus)
    advisor.subscribe(bus)
    profile.subscribe(bus)
    notification.subscribe(bus)


def wire_worker(bus=events.bus) -> None:
    """Subscribers for what the worker publishes (usage.calls.ingested, ingestion.job.*) plus the format adapters."""
    from app.domains.advisor import wiring as advisor
    from app.domains.ingestion import adapters
    from app.domains.notification import wiring as notification
    from app.domains.profile import wiring as profile
    from app.domains.source import wiring as source

    adapters.register_all()
    source.subscribe(bus)
    advisor.subscribe(bus)
    profile.subscribe(bus)
    notification.subscribe(bus)

"""notification.api: the public surface other domains import.

    from app.domains.notification.api import notify
    notify("report.generated", report_id, "리포트가 만들어졌습니다.", workspace_id=ws)

Subscribers for the four MVP events are attached with `wiring.subscribe(bus)` (done in router.py at import).
"""
from __future__ import annotations

from .service import Notification, NotificationError, NotificationService  # noqa: F401
from .wiring import get_service


def notify(kind: str, ref: str | None, text: str, *, user_id: str | None = None, workspace_id: str | None = None):
    return get_service().notify(kind, ref, text, user_id=user_id, workspace_id=workspace_id)


def list_notifications(user_id: str, unread: bool = False):
    return get_service().list(user_id, unread)


def mark_read(user_id: str, notification_id: str) -> None:
    get_service().mark_read(user_id, notification_id)

"""FastAPI routes: /v1/notifications, /v1/notifications/{id}/read, /v1/notification-prefs (current user only)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response

from app.core.events import bus
from app.domains.identity.api import current_user

from .service import NotificationError
from .wiring import get_service, subscribe

router = APIRouter()
subscribe(bus)


def _err(e: NotificationError) -> HTTPException:
    return HTTPException(e.status, detail={"code": e.code, "message": e.message})


def _n(n) -> dict:
    return {"id": n.id, "kind": n.kind, "ref": n.ref, "text": n.text, "created_at": n.created_at.isoformat(),
            "read_at": n.read_at.isoformat() if n.read_at else None}


@router.get("/v1/notifications", tags=["notification"])
def list_notifications(unread: bool = False, user=Depends(current_user)):
    return [_n(n) for n in get_service().list(user.id, unread)]


@router.post("/v1/notifications/{notification}/read", tags=["notification"], status_code=204)
def mark_notification_read(notification: str, user=Depends(current_user)):
    try:
        get_service().mark_read(user.id, notification)
    except NotificationError as e:
        raise _err(e) from None
    return Response(status_code=204)


@router.get("/v1/notification-prefs", tags=["notification"])
def get_notification_prefs(user=Depends(current_user)):
    return get_service().get_prefs(user.id)


@router.put("/v1/notification-prefs", tags=["notification"])
def put_notification_prefs(prefs: list[dict], user=Depends(current_user)):
    try:
        return get_service().put_prefs(user.id, prefs)
    except NotificationError as e:
        raise _err(e) from None

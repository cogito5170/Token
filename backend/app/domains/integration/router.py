"""FastAPI routes: /v1/workspaces/{ws}/integrations, /{ws}/provider-credentials*. Every {ws} route starts with
require_member: viewers list, admins store and revoke (docs/security.md 2).

POST takes the raw JSON object (not a pydantic model) so validation errors never echo a field name or value: a key
pasted into the wrong field must not come back in the 422 body. Request bodies are never logged.
"""
from __future__ import annotations

from fastapi import APIRouter, Body, Depends, Response

from app.domains.identity.api import current_user
from app.domains.workspace.api import require_member

from .api import http_error
from .service import CredentialError
from .wiring import get_service

router = APIRouter()


def _i(i):
    return {"id": i.id, "kind": i.kind, "config": i.config}


@router.get("/v1/workspaces/{ws}/integrations", tags=["integration"])
def list_integrations(ws: str, user=Depends(current_user)):
    require_member(ws, user.id)
    return [_i(i) for i in get_service().integrations(ws)]


@router.get("/v1/workspaces/{ws}/provider-credentials", tags=["integration"])
def list_provider_credentials(ws: str, user=Depends(current_user)):
    require_member(ws, user.id)
    return [c.ref() for c in get_service().credentials(ws)]


@router.post("/v1/workspaces/{ws}/provider-credentials", status_code=201, tags=["integration"])
def store_provider_credential(ws: str, body=Body(...), user=Depends(current_user)):
    require_member(ws, user.id, "admin")
    svc = get_service()
    try:
        provider, secret = svc.parse_create(body)
        return svc.store_credential(ws, user.id, provider, secret).ref()
    except CredentialError as e:
        raise http_error(e) from None


@router.delete("/v1/workspaces/{ws}/provider-credentials/{credential}", status_code=204, tags=["integration"])
def revoke_provider_credential(ws: str, credential: str, user=Depends(current_user)):
    require_member(ws, user.id, "admin")
    try:
        get_service().revoke_credential(ws, user.id, credential)
    except CredentialError as e:
        raise http_error(e) from None
    return Response(status_code=204)

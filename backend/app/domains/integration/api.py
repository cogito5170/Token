"""integration.api: the public surface other domains import (domain-model.md).

    from app.domains.integration.api import use_credential
    with use_credential(ws, credential_id) as key:   # plaintext lives only inside this block
        client = Provider(api_key=key)
Raises HTTPException 404 (unknown, revoked, other workspace), 503 (no KEK configured), 500 (does not decrypt).
"""
from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from fastapi import HTTPException

from .service import PROVIDERS, CredentialError, CredentialRow  # noqa: F401
from .wiring import get_service


def http_error(e: CredentialError) -> HTTPException:
    return HTTPException(e.status, detail={"code": e.code, "message": e.message})


def store_credential(ws: str, actor: str, provider: str, secret: str) -> dict:
    """Returns the CredentialRef dict only."""
    try:
        svc = get_service()
        provider, secret = svc.parse_create({"provider": provider, "secret": secret})
        return svc.store_credential(ws, actor, provider, secret).ref()
    except CredentialError as e:
        raise http_error(e) from None


@contextmanager
def use_credential(ws: str, credential_id: str) -> Iterator[str]:
    try:
        cm = get_service().use_credential(ws, credential_id)
        key = cm.__enter__()
    except CredentialError as e:
        raise http_error(e) from None
    try:
        yield key
    finally:
        del key
        cm.__exit__(None, None, None)


def revoke_credential(ws: str, actor: str, credential_id: str) -> None:
    try:
        get_service().revoke_credential(ws, actor, credential_id)
    except CredentialError as e:
        raise http_error(e) from None

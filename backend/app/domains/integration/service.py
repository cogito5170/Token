"""Integration use cases: provider keys (ADR-0007, docs/security.md 2) and the read-only integrations list.

Store, keyring, audit recorder and event publisher are injected so the rules test without a database.
The secret enters `store_credential`, is sealed at once and leaves only through `use_credential`. Nothing here puts it
(or any part of it but `last4`) in a return value, an exception, a log record, an event or an audit detail.
Role checks (admin to store/revoke, member to list) are the router's, via workspace.api.require_member.
"""
from __future__ import annotations

import logging
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from typing import Callable, Protocol

from . import crypto

log = logging.getLogger(__name__)

PROVIDERS = ("anthropic", "openai", "gemini", "github", "slack")  # docs/schema.sql provider_credentials.provider
CREATE_FIELDS = frozenset({"provider", "secret"})                # openapi CredentialCreate
MIN_SECRET, MAX_SECRET = 16, 4096


class CredentialError(Exception):
    """code: invalid_request | not_found | conflict | key_unavailable | decrypt_failed. Messages are fixed text."""

    def __init__(self, code: str, message: str, status: int):
        super().__init__(message)
        self.code, self.message, self.status = code, message, status


@dataclass
class CredentialRow:
    id: str
    workspace_id: str
    provider: str
    ciphertext: bytes
    nonce: bytes
    wrapped_dek: bytes
    kek_id: str
    fingerprint: str
    last4: str
    created_by: str
    created_at: datetime
    revoked_at: datetime | None = None

    def __repr__(self) -> str:  # dataclass repr would print the sealed bytes into tracebacks
        return f"CredentialRow(id={self.id!r}, provider={self.provider!r}, revoked={self.revoked_at is not None})"

    def ref(self) -> dict:
        """CredentialRef (openapi): the only shape that leaves this domain."""
        return {"id": self.id, "provider": self.provider, "fingerprint": self.fingerprint, "last4": self.last4,
                "created_at": self.created_at, "revoked_at": self.revoked_at}


@dataclass
class IntegrationRow:
    id: str
    workspace_id: str
    kind: str
    config: dict


class Store(Protocol):
    def add(self, c: CredentialRow) -> CredentialRow: ...
    def get(self, ws: str, cred_id: str) -> CredentialRow | None: ...
    def list(self, ws: str) -> list[CredentialRow]: ...
    def active_fingerprint_exists(self, ws: str, fingerprint: str) -> bool: ...
    def revoke(self, ws: str, cred_id: str, at: datetime) -> bool: ...  # wipes ciphertext/nonce/wrapped_dek
    def integrations(self, ws: str) -> list[IntegrationRow]: ...


class MemoryStore:
    def __init__(self) -> None:
        self.rows: dict[str, CredentialRow] = {}
        self.integ: list[IntegrationRow] = []

    def add(self, c):
        self.rows[c.id] = c
        return c

    def get(self, ws, cred_id):
        c = self.rows.get(cred_id)
        return c if c and c.workspace_id == ws else None

    def list(self, ws):
        return sorted((c for c in self.rows.values() if c.workspace_id == ws), key=lambda c: c.created_at)

    def active_fingerprint_exists(self, ws, fingerprint):
        return any(c.workspace_id == ws and c.fingerprint == fingerprint and c.revoked_at is None
                   for c in self.rows.values())

    def revoke(self, ws, cred_id, at):
        c = self.get(ws, cred_id)
        if c is None or c.revoked_at is not None:
            return False
        self.rows[cred_id] = replace(c, ciphertext=b"", nonce=b"", wrapped_dek=b"", revoked_at=at)
        return True

    def integrations(self, ws):
        return [i for i in self.integ if i.workspace_id == ws]


def _aad(ws: str, cred_id: str, provider: str) -> bytes:
    """Binds the ciphertext to its row: copying it to another id, workspace or provider fails to decrypt."""
    return f"gc-credential/1|{ws}|{cred_id}|{provider}".encode()


def _uuid(v) -> str | None:
    try:
        return str(uuid.UUID(str(v)))
    except ValueError:
        return None


def _bad(message: str) -> CredentialError:
    return CredentialError("invalid_request", message, 422)


class IntegrationService:
    def __init__(self, store: Store, keyring, *, audit: Callable[..., object] | None = None,
                 publish: Callable[[str, dict], object] | None = None,
                 now: Callable[[], datetime] = lambda: datetime.now(timezone.utc)) -> None:
        self.store, self.keyring, self.now = store, keyring, now
        self.audit = audit or (lambda *a, **k: None)
        self.publish = publish or (lambda *a, **k: None)

    # ---- provider credentials
    def parse_create(self, body) -> tuple[str, str]:
        """Validate a CredentialCreate body. Unknown fields are refused (a key pasted into the wrong field must not
        be dropped silently or echoed); error messages never quote the input, not even field names."""
        if not isinstance(body, dict):
            raise _bad("body must be an object with provider and secret")
        if set(body) - CREATE_FIELDS:
            raise _bad("only provider and secret are accepted")
        provider, secret = body.get("provider"), body.get("secret")
        if provider not in PROVIDERS:
            raise _bad("provider must be one of " + ", ".join(PROVIDERS))
        if not isinstance(secret, str):
            raise _bad("secret must be a string")
        secret = secret.strip()
        if not (MIN_SECRET <= len(secret) <= MAX_SECRET) or any(ch.isspace() or not ch.isprintable() for ch in secret):
            raise _bad(f"secret must be {MIN_SECRET}-{MAX_SECRET} printable characters without spaces")
        return provider, secret

    def store_credential(self, ws: str, actor: str, provider: str, secret: str) -> CredentialRow:
        try:
            fp = crypto.fingerprint(self.keyring, ws, secret)
            if self.store.active_fingerprint_exists(ws, fp):
                raise CredentialError("conflict", "this key is already stored in the workspace", 409)
            cid = str(uuid.uuid4())
            sealed = crypto.seal(self.keyring, secret.encode(), _aad(ws, cid, provider))
        except crypto.KeyUnavailable:
            log.error("provider key store refused: key-encryption key unavailable")
            raise CredentialError("key_unavailable", "key storage is not configured", 503) from None
        row = self.store.add(CredentialRow(cid, ws, provider, sealed.ciphertext, sealed.nonce, sealed.wrapped_dek,
                                           sealed.kek_id, fp, secret[-4:], actor, self.now()))
        ids = {"workspace_id": ws, "credential_id": row.id}
        self.audit("credential.store", actor, ids, workspace_id=ws, target_kind="provider_credential",
                   target_id=row.id)
        self.publish("integration.credential.stored", ids)
        log.info("provider credential stored id=%s ws=%s", row.id, ws)
        return row

    def credentials(self, ws: str) -> list[CredentialRow]:
        return self.store.list(ws)

    def revoke_credential(self, ws: str, actor: str, cred_id: str) -> None:
        cid = _uuid(cred_id)
        if cid is None or not self.store.revoke(ws, cid, self.now()):
            raise CredentialError("not_found", "no such credential", 404)
        ids = {"workspace_id": ws, "credential_id": cid}
        self.audit("credential.revoke", actor, ids, workspace_id=ws, target_kind="provider_credential", target_id=cid)
        self.publish("integration.credential.revoked", ids)
        log.info("provider credential revoked id=%s ws=%s", cid, ws)

    @contextmanager
    def use_credential(self, ws: str, cred_id: str) -> Iterator[str]:
        """The plaintext exists only inside this block. Revoked, unknown or other-workspace ids are 404."""
        cid = _uuid(cred_id)
        row = self.store.get(ws, cid) if cid else None
        if row is None or row.revoked_at is not None:
            raise CredentialError("not_found", "no such credential", 404)
        try:
            plain = crypto.open_sealed(self.keyring, crypto.Sealed(row.ciphertext, row.nonce, row.wrapped_dek,
                                                                   row.kek_id), _aad(ws, row.id, row.provider))
        except crypto.KeyUnavailable:
            raise CredentialError("key_unavailable", "key storage is not configured", 503) from None
        except crypto.DecryptError:
            log.error("provider credential failed to decrypt id=%s ws=%s", row.id, ws)
            raise CredentialError("decrypt_failed", "stored key could not be decrypted", 500) from None
        yield plain.decode()

    # ---- integrations (read-only: no connect flow in the MVP contract)
    def integrations(self, ws: str) -> list[IntegrationRow]:
        return self.store.integrations(ws)

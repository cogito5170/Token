"""Envelope encryption for provider keys (ADR-0007). AES-256-GCM from `cryptography`; no hand-rolled primitives.

Per credential: a fresh random 256-bit DEK encrypts the secret (AES-GCM, 96-bit nonce, AAD binds the row identity).
The DEK is wrapped by the KEK with AES-GCM too; `wrapped_dek` = wrap nonce || wrapped bytes. The KEK id comes from
`GC_KEK_ID`, its material from `GC_KEK_<id>` (base64 of 32 bytes). Neither value ever appears in code or tests.
Errors carry fixed messages only: never the secret, the key material or the underlying exception text.
"""
from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import os
import re
from collections.abc import Mapping
from dataclasses import dataclass

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

KEK_ID_ENV = "GC_KEK_ID"
KEK_ENV_PREFIX = "GC_KEK_"
KEK_ID_RE = re.compile(r"^[A-Za-z0-9_]{1,32}$")
NONCE_BYTES = 12
KEY_BYTES = 32


class KeyUnavailable(Exception):
    """No usable KEK (id unset or malformed, material missing or not 32 bytes)."""


class DecryptError(Exception):
    """Ciphertext or wrapped DEK does not authenticate under this KEK (wrong KEK, tampered row, wrong context)."""


@dataclass(frozen=True)
class Sealed:
    ciphertext: bytes
    nonce: bytes
    wrapped_dek: bytes
    kek_id: str


def kek_env_name(kek_id: str) -> str:
    if not isinstance(kek_id, str) or not KEK_ID_RE.match(kek_id):
        raise KeyUnavailable("kek id malformed")
    return KEK_ENV_PREFIX + kek_id


class EnvKeyring:
    """KEKs from the environment (development). Production swaps in a KMS-backed object with the same methods."""

    def __init__(self, env: Mapping[str, str] | None = None) -> None:
        self._env = os.environ if env is None else env

    def current_id(self) -> str:
        kid = self._env.get(KEK_ID_ENV) or ""
        kek_env_name(kid)  # validates
        return kid

    def kek(self, kek_id: str) -> bytes:
        raw = self._env.get(kek_env_name(kek_id))
        if not raw:
            raise KeyUnavailable("kek material missing")
        try:
            key = base64.b64decode(raw.strip(), validate=True)
        except (binascii.Error, ValueError):
            raise KeyUnavailable("kek material is not base64") from None
        if len(key) != KEY_BYTES:
            raise KeyUnavailable("kek material must be 32 bytes")
        return key


def _wrap_aad(kek_id: str, aad: bytes) -> bytes:
    return b"gc-dek-wrap/1|" + kek_id.encode() + b"|" + aad


def seal(keyring, plaintext: bytes, aad: bytes) -> Sealed:
    kek_id = keyring.current_id()
    kek = keyring.kek(kek_id)
    dek = AESGCM.generate_key(bit_length=256)
    nonce = os.urandom(NONCE_BYTES)
    ct = AESGCM(dek).encrypt(nonce, plaintext, aad)
    wnonce = os.urandom(NONCE_BYTES)
    wrapped = wnonce + AESGCM(kek).encrypt(wnonce, dek, _wrap_aad(kek_id, aad))
    return Sealed(ct, nonce, wrapped, kek_id)


def open_sealed(keyring, s: Sealed, aad: bytes) -> bytes:
    if not s.ciphertext or not s.wrapped_dek or len(s.wrapped_dek) <= NONCE_BYTES:
        raise DecryptError("nothing to decrypt")
    kek = keyring.kek(s.kek_id)
    try:
        dek = AESGCM(kek).decrypt(s.wrapped_dek[:NONCE_BYTES], s.wrapped_dek[NONCE_BYTES:], _wrap_aad(s.kek_id, aad))
        return AESGCM(dek).decrypt(s.nonce, s.ciphertext, aad)
    except (InvalidTag, ValueError):
        raise DecryptError("decryption failed") from None


def fingerprint(keyring, ws_id: str, secret: str) -> str:
    """HMAC-SHA256 under a subkey derived from the current KEK, scoped to the workspace. Without the KEK it cannot be
    recomputed from a guessed key, and the same key in two workspaces gives unrelated fingerprints."""
    kek_id = keyring.current_id()
    sub = HKDF(algorithm=hashes.SHA256(), length=32, salt=None,
               info=b"gc-credential-fingerprint/1|" + kek_id.encode()).derive(keyring.kek(kek_id))
    mac = hmac.new(sub, ws_id.encode() + b"\x00" + secret.encode(), hashlib.sha256).hexdigest()
    return "hmac-sha256:" + mac[:32]

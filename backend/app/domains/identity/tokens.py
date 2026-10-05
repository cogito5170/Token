"""HS256 access JWT (15 min) without third-party deps; secret comes from the caller (GC_JWT_SECRET)."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time

ACCESS_TTL = 15 * 60
REFRESH_TTL = 30 * 24 * 3600


class TokenError(Exception):
    pass


def _b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def _unb64(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def _sign(secret: str, signing_input: str) -> str:
    return _b64(hmac.new(secret.encode(), signing_input.encode(), hashlib.sha256).digest())


def encode_access(secret: str, user_id: str, now: int | None = None, ttl: int = ACCESS_TTL) -> str:
    if not secret:
        raise TokenError("jwt secret not configured")
    iat = int(time.time() if now is None else now)
    claims = {"sub": user_id, "iat": iat, "exp": iat + ttl, "jti": secrets.token_hex(16)}
    head = _b64(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode())
    body = _b64(json.dumps(claims, separators=(",", ":")).encode())
    return f"{head}.{body}.{_sign(secret, head + '.' + body)}"


def decode_access(secret: str, token: str, now: int | None = None) -> dict:
    if not secret:
        raise TokenError("jwt secret not configured")
    try:
        head, body, sig = token.split(".")
        if not hmac.compare_digest(sig, _sign(secret, head + "." + body)):
            raise TokenError("bad signature")
        if json.loads(_unb64(head)).get("alg") != "HS256":
            raise TokenError("bad alg")
        claims = json.loads(_unb64(body))
    except TokenError:
        raise
    except Exception as e:
        raise TokenError("malformed token") from e
    t = int(time.time() if now is None else now)
    if not isinstance(claims.get("exp"), int) or claims["exp"] <= t:
        raise TokenError("expired")
    if not claims.get("sub"):
        raise TokenError("no subject")
    return claims


def new_refresh_token() -> str:
    return secrets.token_urlsafe(32)  # 256-bit opaque


def hash_refresh(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()

"""Identity use cases. Store, hasher, clock and audit recorder are injected so the rules test without a DB.

Audit: `audit(action, actor_user_id, detail)` — fake until audit.api.record (GC15). detail holds ids/counts only.
"""
from __future__ import annotations

import time
import uuid
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Callable, Protocol

from . import tokens
from .passwords import check_policy

LOGIN_LIMIT = 10
LOGIN_WINDOW = 15 * 60


class AuthError(Exception):
    """code: invalid_credentials | rate_limited | invalid_refresh | email_taken | invalid_token | weak_password"""

    def __init__(self, code: str, message: str, status: int):
        super().__init__(message)
        self.code, self.message, self.status = code, message, status


@dataclass
class UserRow:
    id: str
    email: str
    display_name: str
    password_hash: str
    disabled: bool = False


@dataclass
class RefreshRow:
    id: str
    user_id: str
    token_hash: str
    family_id: str
    expires_at: float
    rotated_at: float | None = None
    revoked_at: float | None = None


class Store(Protocol):
    def create_user(self, email: str, display_name: str, password_hash: str) -> UserRow | None: ...  # None if taken
    def user_by_email(self, email: str) -> UserRow | None: ...
    def user_by_id(self, user_id: str) -> UserRow | None: ...
    def add_refresh(self, row: RefreshRow) -> None: ...
    def refresh_by_hash(self, token_hash: str) -> RefreshRow | None: ...
    def mark_rotated(self, row_id: str, at: float) -> bool: ...  # False if already rotated (race)
    def revoke_family(self, family_id: str, at: float) -> None: ...


class MemoryStore:
    def __init__(self) -> None:
        self.users: dict[str, UserRow] = {}
        self.refresh: dict[str, RefreshRow] = {}

    def create_user(self, email, display_name, password_hash):
        if self.user_by_email(email):
            return None
        u = UserRow(str(uuid.uuid4()), email, display_name, password_hash)
        self.users[u.id] = u
        return u

    def user_by_email(self, email):
        return next((u for u in self.users.values() if u.email.lower() == email.lower()), None)

    def user_by_id(self, user_id):
        return self.users.get(user_id)

    def add_refresh(self, row):
        self.refresh[row.token_hash] = row

    def refresh_by_hash(self, token_hash):
        return self.refresh.get(token_hash)

    def mark_rotated(self, row_id, at):
        for r in self.refresh.values():
            if r.id == row_id:
                if r.rotated_at is not None:
                    return False
                r.rotated_at = at
                return True
        return False

    def revoke_family(self, family_id, at):
        for r in self.refresh.values():
            if r.family_id == family_id and r.revoked_at is None:
                r.revoked_at = at


class RateLimiter:
    """Sliding window per key: `limit` attempts per `window` seconds."""

    def __init__(self, limit: int = LOGIN_LIMIT, window: int = LOGIN_WINDOW, clock: Callable[[], float] = time.time):
        self.limit, self.window, self.clock = limit, window, clock
        self._hits: dict[str, deque] = defaultdict(deque)

    def hit(self, key: str) -> bool:
        """Record an attempt; False when it exceeds the limit (refused attempts are not counted)."""
        now = self.clock()
        q = self._hits[key]
        while q and q[0] <= now - self.window:
            q.popleft()
        if len(q) >= self.limit:
            return False
        q.append(now)
        return True


@dataclass
class Tokens:
    access_token: str
    expires_in: int
    refresh_token: str = field(repr=False)


def _noop_audit(action: str, actor: str | None, detail: dict) -> None:
    return None


def normalize_email(email: str) -> str:
    e = (email or "").strip()
    if e.count("@") != 1 or e.startswith("@") or e.endswith("@") or len(e) > 254 or any(c.isspace() for c in e):
        raise AuthError("invalid_email", "invalid email", 422)
    return e


class IdentityService:
    def __init__(self, store: Store, hasher, jwt_secret: str, audit=_noop_audit, publish=None,
                 limiter: RateLimiter | None = None, clock: Callable[[], float] = time.time):
        self.store, self.hasher, self.secret = store, hasher, jwt_secret
        self.audit, self.publish, self.clock = audit, publish, clock
        self.limiter = limiter or RateLimiter(clock=clock)

    def _issue(self, user_id: str, family_id: str | None = None) -> Tokens:
        now = self.clock()
        raw = tokens.new_refresh_token()
        self.store.add_refresh(RefreshRow(str(uuid.uuid4()), user_id, tokens.hash_refresh(raw),
                                          family_id or str(uuid.uuid4()), now + tokens.REFRESH_TTL))
        return Tokens(tokens.encode_access(self.secret, user_id, now=int(now)), tokens.ACCESS_TTL, raw)

    def signup(self, email: str, password: str, display_name: str = "") -> Tokens:
        email = normalize_email(email)
        try:
            check_policy(password)
        except ValueError as e:
            raise AuthError("weak_password", str(e), 422) from None
        u = self.store.create_user(email, display_name or "", self.hasher.hash(password))
        if u is None:
            raise AuthError("email_taken", "email already registered", 409)
        if self.publish:
            self.publish("identity.user.created", {"user_id": u.id})
        return self._issue(u.id)

    def login(self, email: str, password: str, ip: str = "") -> Tokens:
        key = f"{ip}|{(email or '').strip().lower()}"
        if not self.limiter.hit(key):
            raise AuthError("rate_limited", "too many login attempts", 429)
        u = self.store.user_by_email((email or "").strip())
        ok = bool(u) and not u.disabled and self.hasher.verify(u.password_hash, password)
        if not ok:
            self.audit("auth.login_failed", u.id if u else None, {})
            raise AuthError("invalid_credentials", "invalid email or password", 401)
        self.audit("auth.login", u.id, {})
        return self._issue(u.id)

    def refresh(self, raw_token: str | None) -> Tokens:
        bad = AuthError("invalid_refresh", "invalid refresh token", 401)
        if not raw_token:
            raise bad
        row = self.store.refresh_by_hash(tokens.hash_refresh(raw_token))
        now = self.clock()
        if row is None:
            raise bad
        if row.rotated_at is not None:  # reuse of a rotated token: burn the whole family
            self.store.revoke_family(row.family_id, now)
            self.audit("auth.refresh_reuse", row.user_id, {"family_id": row.family_id})
            raise bad
        if row.revoked_at is not None or row.expires_at <= now:
            raise bad
        u = self.store.user_by_id(row.user_id)
        if u is None or u.disabled:
            raise bad
        if not self.store.mark_rotated(row.id, now):  # lost a concurrent rotation: same as reuse
            self.store.revoke_family(row.family_id, now)
            self.audit("auth.refresh_reuse", row.user_id, {"family_id": row.family_id})
            raise bad
        return self._issue(row.user_id, row.family_id)

    def logout(self, raw_token: str | None) -> None:
        if not raw_token:
            return
        row = self.store.refresh_by_hash(tokens.hash_refresh(raw_token))
        if row:
            self.store.revoke_family(row.family_id, self.clock())

    def authenticate(self, access_token: str) -> UserRow:
        try:
            claims = tokens.decode_access(self.secret, access_token, now=int(self.clock()))
        except tokens.TokenError:
            raise AuthError("invalid_token", "invalid or expired token", 401) from None
        u = self.store.user_by_id(claims["sub"])
        if u is None or u.disabled:
            raise AuthError("invalid_token", "invalid or expired token", 401)
        return u

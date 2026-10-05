"""Argon2id hashing (m=64 MiB, t=3, p=1) and the password policy (security.md section 6)."""
from __future__ import annotations

MIN_LENGTH = 12
COMMON = frozenset(
    p.lower()
    for p in (
        "password1234", "passwordpassword", "123456789012", "1234567890123", "qwertyuiop12", "qwertyuiopas",
        "letmein12345", "iloveyou1234", "administrator", "welcome12345", "changeme1234", "password12345",
        "abcdefghijkl", "111111111111", "000000000000", "123456123456",
    )
)


class PasswordPolicyError(ValueError):
    pass


def check_policy(password: str) -> None:
    if len(password) < MIN_LENGTH:
        raise PasswordPolicyError("password must be at least 12 characters")
    if password.lower() in COMMON or len(set(password)) < 4:
        raise PasswordPolicyError("password is too common")


class Argon2Hasher:
    """Needs argon2-cffi; constructed lazily so the module imports without it."""

    def __init__(self) -> None:
        from argon2 import PasswordHasher, Type

        self._ph = PasswordHasher(time_cost=3, memory_cost=64 * 1024, parallelism=1, type=Type.ID)

    def hash(self, password: str) -> str:
        return self._ph.hash(password)

    def verify(self, hashed: str, password: str) -> bool:
        from argon2.exceptions import InvalidHashError, VerificationError

        try:
            return self._ph.verify(hashed, password)
        except (VerificationError, InvalidHashError):
            return False

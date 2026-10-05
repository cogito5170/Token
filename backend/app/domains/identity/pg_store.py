"""PostgreSQL Store over the `users` / `refresh_tokens` tables (docs/schema.sql). psycopg imported lazily."""
from __future__ import annotations

from datetime import datetime, timezone

from .service import RefreshRow, UserRow


def _ts(x: float | None):
    return None if x is None else datetime.fromtimestamp(x, tz=timezone.utc)


def _f(d):
    return None if d is None else d.timestamp()


class PgStore:
    def __init__(self, pool) -> None:
        self.pool = pool

    @staticmethod
    def _user(r):
        return None if r is None else UserRow(str(r[0]), r[1], r[2], r[3], r[4] is not None)

    def create_user(self, email, display_name, password_hash):
        with self.pool.connection() as c:
            r = c.execute(
                "INSERT INTO users (email, display_name, password_hash) VALUES (%s,%s,%s) "
                "ON CONFLICT DO NOTHING RETURNING id, email, display_name, password_hash, disabled_at",
                (email, display_name, password_hash)).fetchone()
        return self._user(r)

    def user_by_email(self, email):
        with self.pool.connection() as c:
            return self._user(c.execute(
                "SELECT id, email, display_name, password_hash, disabled_at FROM users WHERE lower(email)=lower(%s)",
                (email,)).fetchone())

    def user_by_id(self, user_id):
        with self.pool.connection() as c:
            return self._user(c.execute(
                "SELECT id, email, display_name, password_hash, disabled_at FROM users WHERE id=%s",
                (user_id,)).fetchone())

    def add_refresh(self, row):
        with self.pool.connection() as c:
            c.execute(
                "INSERT INTO refresh_tokens (id, user_id, token_hash, family_id, expires_at) VALUES (%s,%s,%s,%s,%s)",
                (row.id, row.user_id, row.token_hash, row.family_id, _ts(row.expires_at)))

    def refresh_by_hash(self, token_hash):
        with self.pool.connection() as c:
            r = c.execute(
                "SELECT id, user_id, token_hash, family_id, expires_at, rotated_at, revoked_at "
                "FROM refresh_tokens WHERE token_hash=%s", (token_hash,)).fetchone()
        return None if r is None else RefreshRow(str(r[0]), str(r[1]), r[2], str(r[3]), _f(r[4]), _f(r[5]), _f(r[6]))

    def mark_rotated(self, row_id, at):
        with self.pool.connection() as c:
            cur = c.execute("UPDATE refresh_tokens SET rotated_at=%s WHERE id=%s AND rotated_at IS NULL",
                            (_ts(at), row_id))
            return cur.rowcount == 1

    def revoke_family(self, family_id, at):
        with self.pool.connection() as c:
            c.execute("UPDATE refresh_tokens SET revoked_at=%s WHERE family_id=%s AND revoked_at IS NULL",
                      (_ts(at), family_id))

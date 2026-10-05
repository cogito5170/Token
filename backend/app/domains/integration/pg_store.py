"""PostgreSQL Store over provider_credentials / integrations (docs/schema.sql). Pool is injected.

Revoke wipes ciphertext, nonce and wrapped_dek in the same UPDATE that sets revoked_at (crypto-shredding): the row
stays as the reference the audit log points at, but nothing decryptable is left.
"""
from __future__ import annotations

from .service import CredentialRow, IntegrationRow

_C = "id, workspace_id, provider, ciphertext, nonce, wrapped_dek, kek_id, fingerprint, last4, created_by, created_at, revoked_at"


class PgStore:
    def __init__(self, pool) -> None:
        self.pool = pool

    @staticmethod
    def _c(r):
        return CredentialRow(str(r[0]), str(r[1]), r[2], bytes(r[3]), bytes(r[4]), bytes(r[5]), r[6], r[7], r[8],
                             str(r[9]), r[10], r[11])

    def add(self, c):
        with self.pool.connection() as conn:
            r = conn.execute(f"INSERT INTO provider_credentials (id, workspace_id, provider, ciphertext, nonce, wrapped_dek, "
                             f"kek_id, fingerprint, last4, created_by, created_at) "
                             f"VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING {_C}",
                             (c.id, c.workspace_id, c.provider, c.ciphertext, c.nonce, c.wrapped_dek, c.kek_id,
                              c.fingerprint, c.last4, c.created_by, c.created_at)).fetchone()
        return self._c(r)

    def get(self, ws, cred_id):
        with self.pool.connection() as conn:
            r = conn.execute(f"SELECT {_C} FROM provider_credentials WHERE workspace_id=%s AND id=%s",
                             (ws, cred_id)).fetchone()
        return None if r is None else self._c(r)

    def list(self, ws):
        with self.pool.connection() as conn:
            rows = conn.execute(f"SELECT {_C} FROM provider_credentials WHERE workspace_id=%s ORDER BY created_at, id",
                                (ws,)).fetchall()
        return [self._c(r) for r in rows]

    def active_fingerprint_exists(self, ws, fingerprint):
        with self.pool.connection() as conn:
            return conn.execute("SELECT 1 FROM provider_credentials WHERE workspace_id=%s AND fingerprint=%s "
                                "AND revoked_at IS NULL LIMIT 1", (ws, fingerprint)).fetchone() is not None

    def revoke(self, ws, cred_id, at):
        with self.pool.connection() as conn:
            r = conn.execute("UPDATE provider_credentials SET ciphertext='', nonce='', wrapped_dek='', revoked_at=%s "
                             "WHERE workspace_id=%s AND id=%s AND revoked_at IS NULL RETURNING id",
                             (at, ws, cred_id)).fetchone()
        return r is not None

    def integrations(self, ws):
        with self.pool.connection() as conn:
            rows = conn.execute("SELECT id, workspace_id, kind, config FROM integrations WHERE workspace_id=%s "
                                "ORDER BY created_at, id", (ws,)).fetchall()
        return [IntegrationRow(str(r[0]), str(r[1]), r[2], r[3] or {}) for r in rows]

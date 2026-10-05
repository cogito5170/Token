"""PostgreSQL Store over notifications / notification_prefs (docs/schema.sql)."""
from __future__ import annotations

from .service import Notification

_COLS = "id, user_id, workspace_id, kind, ref, text, created_at, read_at"


def _row(r) -> Notification:
    return Notification(str(r[0]), str(r[1]), None if r[2] is None else str(r[2]), r[3], r[4], r[5], r[6], r[7])


class PgStore:
    def __init__(self, pool) -> None:
        self.pool = pool

    def add(self, n: Notification) -> Notification:
        with self.pool.connection() as c:
            r = c.execute(
                "INSERT INTO notifications (id, user_id, workspace_id, kind, ref, text, created_at) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING " + _COLS,
                (n.id, n.user_id, n.workspace_id, n.kind, n.ref, n.text, n.created_at)).fetchone()
        return _row(r)

    def list(self, user_id, unread, limit):
        sql = "SELECT " + _COLS + " FROM notifications WHERE user_id=%s" + (" AND read_at IS NULL" if unread else "")
        with self.pool.connection() as c:
            return [_row(r) for r in c.execute(sql + " ORDER BY created_at DESC, id LIMIT %s", (user_id, limit))]

    def mark_read(self, user_id, nid, at) -> bool:
        with self.pool.connection() as c:
            return c.execute("UPDATE notifications SET read_at = COALESCE(read_at, %s) WHERE id=%s AND user_id=%s "
                             "RETURNING id", (at, nid, user_id)).fetchone() is not None

    def get_prefs(self, user_id):
        with self.pool.connection() as c:
            return [(r[0], r[1], r[2]) for r in c.execute(
                "SELECT kind, channel, enabled FROM notification_prefs WHERE user_id=%s ORDER BY kind, channel",
                (user_id,))]

    def put_prefs(self, user_id, prefs) -> None:
        with self.pool.connection() as c:
            for k, ch, e in prefs:
                c.execute("INSERT INTO notification_prefs (user_id, kind, channel, enabled) VALUES (%s,%s,%s,%s) "
                          "ON CONFLICT (user_id, kind, channel) DO UPDATE SET enabled=EXCLUDED.enabled",
                          (user_id, k, ch, e))

    def enabled(self, user_id, kind, channel) -> bool:
        with self.pool.connection() as c:
            r = c.execute("SELECT enabled FROM notification_prefs WHERE user_id=%s AND kind=%s AND channel=%s",
                          (user_id, kind, channel)).fetchone()
        return True if r is None else bool(r[0])

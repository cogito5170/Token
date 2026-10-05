"""PostgreSQL Store over audit_log (docs/schema.sql). INSERT and SELECT only; the DB trigger refuses UPDATE/DELETE."""
from __future__ import annotations

import json

from .service import AuditRow

_COLS = "id, at, workspace_id, actor_user_id, actor_kind, action, target_kind, target_id, detail, request_id"


def _row(r) -> AuditRow:
    return AuditRow(int(r[0]), r[1], None if r[2] is None else str(r[2]), None if r[3] is None else str(r[3]),
                    r[4], r[5], r[6], r[7], r[8] if isinstance(r[8], dict) else json.loads(r[8]), r[9])


class PgStore:
    def __init__(self, pool) -> None:
        self.pool = pool

    def append(self, row: AuditRow) -> AuditRow:
        with self.pool.connection() as c:
            r = c.execute(
                "INSERT INTO audit_log (workspace_id, actor_user_id, actor_kind, action, target_kind, target_id, "
                "detail, request_id) VALUES (%s,%s,%s,%s,%s,%s,%s::jsonb,%s) RETURNING " + _COLS,
                (row.workspace_id, row.actor_user_id, row.actor_kind, row.action, row.target_kind, row.target_id,
                 json.dumps(row.detail), row.request_id)).fetchone()
        return _row(r)

    def query(self, ws, action, frm, to, before, limit):
        sql, args = "SELECT " + _COLS + " FROM audit_log WHERE workspace_id=%s", [ws]
        for cond, val in (("action=%s", action), ("at>=%s", frm), ("at<=%s", to), ("id<%s", before)):
            if val is not None:
                sql += " AND " + cond
                args.append(val)
        with self.pool.connection() as c:
            return [_row(r) for r in c.execute(sql + " ORDER BY id DESC LIMIT %s", (*args, limit)).fetchall()]

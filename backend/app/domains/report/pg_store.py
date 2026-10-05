"""PostgreSQL Store over reports (docs/schema.sql)."""
from __future__ import annotations

import json

from .service import ReportRow

_C = "id, workspace_id, period_start, period_end, generated_by, body, created_at"


def _r(r) -> ReportRow:
    return ReportRow(str(r[0]), str(r[1]), r[2], r[3], None if r[4] is None else str(r[4]),
                     r[5] if isinstance(r[5], dict) else json.loads(r[5]), r[6])


class PgStore:
    def __init__(self, pool) -> None:
        self.pool = pool

    def add(self, r: ReportRow) -> ReportRow:
        with self.pool.connection() as c:
            row = c.execute("INSERT INTO reports (id, workspace_id, period_start, period_end, generated_by, body,"
                            " created_at) VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING " + _C,
                            (r.id, r.workspace_id, r.period_start, r.period_end, r.generated_by,
                             json.dumps(r.body), r.created_at)).fetchone()
        return _r(row)

    def get(self, ws, rid):
        with self.pool.connection() as c:
            row = c.execute("SELECT " + _C + " FROM reports WHERE workspace_id=%s AND id=%s", (ws, rid)).fetchone()
        return _r(row) if row else None

    def list(self, ws):
        with self.pool.connection() as c:
            return [_r(x) for x in c.execute("SELECT " + _C + " FROM reports WHERE workspace_id=%s"
                                             " ORDER BY created_at DESC", (ws,)).fetchall()]

"""PostgreSQL Store over budgets / budget_alerts (docs/schema.sql)."""
from __future__ import annotations

from .service import Alert, Budget

_B = "id, workspace_id, scope, period, measure, limit_microusd, thresholds, action_at_limit, project_id, created_by, archived_at"


def _b(r) -> Budget:
    s = lambda v: None if v is None else str(v)  # noqa: E731
    return Budget(str(r[0]), str(r[1]), r[2], r[3], r[4], int(r[5]), [int(t) for t in r[6]], r[7], s(r[8]), s(r[9]),
                  r[10])


class PgStore:
    def __init__(self, pool) -> None:
        self.pool = pool

    def add_budget(self, b: Budget) -> Budget:
        with self.pool.connection() as c:
            r = c.execute(
                "INSERT INTO budgets (workspace_id, project_id, scope, period, measure, limit_microusd, thresholds,"
                " action_at_limit, created_by) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING " + _B,
                (b.workspace_id, b.project_id, b.scope, b.period, b.measure, b.limit_microusd, b.thresholds,
                 b.action_at_limit, b.created_by)).fetchone()
        return _b(r)

    def get_budget(self, ws, bid):
        with self.pool.connection() as c:
            r = c.execute("SELECT " + _B + " FROM budgets WHERE workspace_id=%s AND id=%s", (ws, bid)).fetchone()
        return _b(r) if r else None

    def list_budgets(self, ws, include_archived=False):
        sql = "SELECT " + _B + " FROM budgets WHERE workspace_id=%s" + ("" if include_archived else
                                                                       " AND archived_at IS NULL")
        with self.pool.connection() as c:
            return [_b(r) for r in c.execute(sql + " ORDER BY created_at", (ws,)).fetchall()]

    def archive(self, ws, bid, at) -> bool:
        with self.pool.connection() as c:
            return c.execute("UPDATE budgets SET archived_at=%s WHERE workspace_id=%s AND id=%s AND archived_at IS NULL",
                             (at, ws, bid)).rowcount > 0

    def add_alert(self, a: Alert) -> bool:
        with self.pool.connection() as c:
            return c.execute(
                "INSERT INTO budget_alerts (budget_id, period_start, threshold, used_microusd, raised_at)"
                " VALUES (%s,%s,%s,%s,%s) ON CONFLICT (budget_id, period_start, threshold) DO NOTHING",
                (a.budget_id, a.period_start, a.threshold, a.used_microusd, a.raised_at)).rowcount > 0

    def list_alerts(self, ws):
        with self.pool.connection() as c:
            rows = c.execute(
                "SELECT a.id, a.budget_id, a.period_start, a.threshold, a.used_microusd, a.raised_at FROM budget_alerts a"
                " JOIN budgets b ON b.id=a.budget_id WHERE b.workspace_id=%s ORDER BY a.raised_at DESC", (ws,)).fetchall()
        return [Alert(str(r[0]), str(r[1]), r[2], int(r[3]), int(r[4]), r[5]) for r in rows]

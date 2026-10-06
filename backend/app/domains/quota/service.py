"""Quota use cases: budgets in both cost measures, burn projection, threshold alerts, the proposal gate check().

Usage is injected (`summary(ws, t_from, t_to, project)` of usage.api) so rules test without a DB. Both measures
(list price, CLI cost) are always returned side by side; `used.cli.value` is null while no call reported it and
`coverage_permille` (< 1000 when some calls lack cli cost) comes straight from usage.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field, replace
from datetime import date, datetime, timedelta, timezone
from typing import Callable

SCOPES = ("workspace", "project", "task")
PERIODS = ("day", "month", "task")
MEASURES = ("list", "cli")
ACTIONS = ("alert", "stop")
DEFAULT_THRESHOLDS = (50, 80, 100)
TASK_WINDOW_DAYS = 30


class QuotaError(Exception):
    """code: not_found | invalid_request"""

    def __init__(self, code: str, message: str, status: int):
        super().__init__(message)
        self.code, self.message, self.status = code, message, status


@dataclass
class Budget:
    id: str
    workspace_id: str
    scope: str
    period: str
    measure: str
    limit_microusd: int
    thresholds: list[int]
    action_at_limit: str = "alert"
    project_id: str | None = None
    created_by: str | None = None
    archived_at: datetime | None = None


@dataclass
class Alert:
    id: str
    budget_id: str
    period_start: date
    threshold: int
    used_microusd: int
    raised_at: datetime


class MemoryStore:
    def __init__(self) -> None:
        self.budgets: dict[str, Budget] = {}
        self.alerts: list[Alert] = []

    def add_budget(self, b: Budget) -> Budget:
        self.budgets[b.id] = b
        return b

    def get_budget(self, ws: str, bid: str) -> Budget | None:
        b = self.budgets.get(bid)
        return b if b and b.workspace_id == ws else None

    def list_budgets(self, ws: str, include_archived: bool = False) -> list[Budget]:
        return [b for b in self.budgets.values()
                if b.workspace_id == ws and (include_archived or b.archived_at is None)]

    def archive(self, ws: str, bid: str, at: datetime) -> bool:
        b = self.get_budget(ws, bid)
        if b is None or b.archived_at is not None:
            return False
        self.budgets[bid] = replace(b, archived_at=at)
        return True

    def add_alert(self, a: Alert) -> bool:
        """False when (budget, period_start, threshold) was already raised (UNIQUE in the schema)."""
        if any((x.budget_id, x.period_start, x.threshold) == (a.budget_id, a.period_start, a.threshold)
               for x in self.alerts):
            return False
        self.alerts.append(a)
        return True

    def list_alerts(self, ws: str) -> list[Alert]:
        ids = {b.id for b in self.budgets.values() if b.workspace_id == ws}
        return sorted((a for a in self.alerts if a.budget_id in ids), key=lambda a: a.raised_at, reverse=True)


def _metric(value, prov, coverage=None) -> dict:
    m = {"value": value, "unit": "microusd", "provenance": prov}
    if coverage is not None:
        m["coverage_permille"] = coverage
    return m


def _iso(d: datetime) -> str:
    return d.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _pct(vals: list[int], q: int) -> int:
    s = sorted(vals)
    return s[min(len(s) - 1, (len(s) * q) // 100)] if s else 0


class QuotaService:
    def __init__(self, store, summary: Callable, now: Callable[[], datetime] | None = None,
                 notify: Callable[[Budget, Alert], None] | None = None,
                 audit: Callable[..., object] | None = None) -> None:
        self.store, self.summary = store, summary
        self.now = now or (lambda: datetime.now(timezone.utc))
        self.notify, self.audit = notify, audit

    # -- budgets ---------------------------------------------------------------------------------------------
    def create(self, ws: str, actor: str | None, scope: str, period: str, measure: str, limit_microusd: int,
               project_id: str | None = None, thresholds=None, action_at_limit: str = "alert") -> Budget:
        raw_th = thresholds if thresholds else DEFAULT_THRESHOLDS
        try:
            if any(not isinstance(t, int) or isinstance(t, bool) for t in raw_th):
                raise QuotaError("invalid_request", "invalid budget", 422)
            th = sorted(set(raw_th))
        except TypeError:
            raise QuotaError("invalid_request", "invalid budget", 422)
        bad = (scope not in SCOPES or period not in PERIODS or measure not in MEASURES
               or action_at_limit not in ACTIONS or not isinstance(limit_microusd, int) or limit_microusd < 1
               or any(not 1 <= t <= 100 for t in th)
               or (scope == "project" and not project_id) or (scope != "project" and project_id)
               or (scope == "task") != (period == "task"))
        if bad:
            raise QuotaError("invalid_request", "invalid budget", 422)
        b = self.store.add_budget(Budget(str(uuid.uuid4()), ws, scope, period, measure, limit_microusd, th,
                                         action_at_limit, project_id, actor))
        if self.audit:
            self.audit("budget.create", actor, {"workspace_id": ws, "budget_id": b.id, "scope": scope,
                                                "period": period, "measure": measure,
                                                "limit_microusd": limit_microusd}, workspace_id=ws,
                       target_kind="budget", target_id=b.id)
        return b

    def get(self, ws: str, bid: str) -> Budget:
        b = self.store.get_budget(ws, bid)
        if b is None:
            raise QuotaError("not_found", "budget not found", 404)
        return b

    def archive(self, ws: str, bid: str, actor: str | None = None) -> None:
        if not self.store.archive(ws, bid, self.now()):
            raise QuotaError("not_found", "budget not found", 404)
        if self.audit:
            self.audit("budget.archive", actor, {"workspace_id": ws, "budget_id": bid}, workspace_id=ws,
                       target_kind="budget", target_id=bid)

    # -- use ---------------------------------------------------------------------------------------------------
    def period_window(self, b: Budget) -> tuple[datetime, datetime]:
        now = self.now().astimezone(timezone.utc)
        day0 = now.replace(hour=0, minute=0, second=0, microsecond=0)
        if b.period == "day":
            return day0, day0 + timedelta(days=1)
        if b.period == "month":
            m0 = day0.replace(day=1)
            nxt = (m0 + timedelta(days=32)).replace(day=1)
            return m0, nxt
        return day0 - timedelta(days=TASK_WINDOW_DAYS - 1), day0 + timedelta(days=1)

    def _summary(self, b: Budget) -> dict:
        frm, to = self.period_window(b)
        return self.summary(b.workspace_id, frm, min(to, self.now()), b.project_id)

    @staticmethod
    def _used(s: dict) -> dict:
        t = s["tiles"]
        return {"list": _metric(t["cost_list"]["value"], "CALCULATED"),
                "cli": _metric(t["cost_cli"]["value"], "MEASURED", t["cost_cli"].get("coverage_permille", 0))}

    def used(self, b: Budget) -> dict:
        return self._used(self._summary(b))

    def view(self, b: Budget) -> dict:
        return {"id": b.id, "scope": b.scope, "project_id": b.project_id, "period": b.period, "measure": b.measure,
                "limit_microusd": b.limit_microusd, "thresholds": list(b.thresholds),
                "action_at_limit": b.action_at_limit, "used": self.used(b)}

    def list(self, ws: str) -> list[dict]:
        return [self.view(b) for b in self.store.list_budgets(ws)]

    # -- burn ----------------------------------------------------------------------------------------------------
    def burn(self, ws: str, bid: str) -> dict:
        b = self.get(ws, bid)
        s = self._summary(b)
        frm, end = self.period_window(b)
        by = {x["name"]: x["points"] for x in s["trend"]["series"]}
        cum = {}
        for m, name in (("list", "cost_list"), ("cli", "cost_cli")):
            run, pts = 0, []
            for ts, v in by.get(name, []):
                run += v or 0
                pts.append([ts, run if (v is not None or m == "list" or pts) else None])
            cum[m] = {"name": f"cumulative_{m}", "unit": "microusd",
                      "provenance": "CALCULATED" if m == "list" else "MEASURED", "points": pts}
        pts = cum[b.measure]["points"]
        daily = [pts[i][1] - (pts[i - 1][1] if i else 0) for i in range(len(pts)) if pts[i][1] is not None]
        last = self.now().astimezone(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        base = pts[-1][1] if pts and pts[-1][1] is not None else 0
        horizon = max(0, (end - last).days) if b.period != "task" else TASK_WINDOW_DAYS
        proj, exh = {}, {}
        for name, q in (("p10", 10), ("p50", 50), ("p90", 90)):
            rate, run, out, hit = _pct(daily, q), base, [], None
            for i in range(1, horizon + 1):
                run += rate
                day = last + timedelta(days=i)
                out.append([_iso(day), run])
                if hit is None and run >= b.limit_microusd:
                    hit = _iso(day)
            if base >= b.limit_microusd:
                hit = pts[-1][0]
            proj[name] = {"name": f"projection_{name}", "unit": "microusd", "provenance": "CALCULATED",
                          "points": out}
            exh[f"exhaust_at_{name}"] = hit
        return {"budget_id": b.id, "limit_microusd": b.limit_microusd, "cumulative": cum,
                "projection": {**proj, **exh}}

    # -- alerts ----------------------------------------------------------------------------------------------------
    def evaluate(self, ws: str) -> list[Alert]:
        """Raise each crossed threshold once per budget and period (the UNIQUE key makes repeats no-ops)."""
        raised = []
        for b in self.store.list_budgets(ws):
            used = self.used(b)[b.measure]["value"]
            if used is None:
                continue
            start = self.period_window(b)[0].date()
            for th in sorted(b.thresholds):
                if used * 100 >= b.limit_microusd * th:
                    a = Alert(str(uuid.uuid4()), b.id, start, th, used, self.now())
                    if self.store.add_alert(a):
                        raised.append(a)
                        if self.notify:
                            self.notify(b, a)
        return raised

    def alerts(self, ws: str) -> list[dict]:
        return [{"id": a.id, "budget_id": a.budget_id, "threshold": a.threshold, "used_microusd": a.used_microusd,
                 "raised_at": _iso(a.raised_at)} for a in self.store.list_alerts(ws)]

    # -- proposal gate ---------------------------------------------------------------------------------------------
    def check(self, ws: str, scope: str, extra_cost: int, project_id: str | None = None,
              cost_cli: int | None = None) -> dict:
        """Would `extra_cost` (list micro-USD; `cost_cli` for cli budgets, default = extra_cost) break a budget?"""
        if scope not in SCOPES or not isinstance(extra_cost, int) or extra_cost < 0:
            raise QuotaError("invalid_request", "invalid check", 422)
        extra = {"list": extra_cost, "cli": extra_cost if cost_cli is None else cost_cli}
        blocked = []
        for b in self.store.list_budgets(ws):
            if b.scope != scope or (scope == "project" and b.project_id != project_id):
                continue
            used = self.used(b)[b.measure]["value"] or 0
            after = used + extra[b.measure]
            if after > b.limit_microusd:
                blocked.append({"budget_id": b.id, "measure": b.measure, "limit_microusd": b.limit_microusd,
                                "used_microusd": used, "after_microusd": after,
                                "action_at_limit": b.action_at_limit})
        return {"allowed": not blocked, "blocked_by": blocked}

"""Report use cases: build a period report from usage / advisor / quota interfaces only, store it, export JSON / CSV.

Every number in a report is a dict {value, unit, provenance, source[, coverage_permille]}; the flat `rows` list is
derived from the body once, and both exports render that same list, so JSON and CSV cannot disagree. Exporting is
audited (`report.export`, ids and counts only). No prompt bodies are ever read or stored.
"""
from __future__ import annotations

import csv
import io
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Callable

CSV_COLUMNS = ("section", "key", "value", "unit", "provenance", "source", "coverage_permille")
FORMATS = ("json", "csv")
RANK = {"viewer": 0, "developer": 1, "admin": 2}


class ReportError(Exception):
    """code: not_found | invalid_request"""

    def __init__(self, code: str, message: str, status: int):
        super().__init__(message)
        self.code, self.message, self.status = code, message, status


@dataclass
class ReportRow:
    id: str
    workspace_id: str
    period_start: date
    period_end: date
    generated_by: str | None
    body: dict
    created_at: datetime


class MemoryStore:
    def __init__(self) -> None:
        self.reports: dict[str, ReportRow] = {}

    def add(self, r: ReportRow) -> ReportRow:
        self.reports[r.id] = r
        return r

    def get(self, ws, rid) -> ReportRow | None:
        r = self.reports.get(rid)
        return r if r and r.workspace_id == ws else None

    def list(self, ws) -> list[ReportRow]:
        return sorted((r for r in self.reports.values() if r.workspace_id == ws), key=lambda r: r.created_at,
                      reverse=True)


def num(value, unit, provenance, source, coverage=None) -> dict:
    n = {"value": value, "unit": unit, "provenance": provenance, "source": source}
    if coverage is not None:
        n["coverage_permille"] = coverage
    return n


def _tile(t: dict | None, source: str) -> dict:
    t = t or {}
    return num(t.get("value"), t.get("unit", ""), t.get("provenance", "CALCULATED"), source, t.get("coverage_permille"))


def flatten(body: dict) -> list[dict]:
    """The single flat view of a report body: one row per number (section, key, value, unit, provenance, source)."""
    rows = []
    for section in ("usage", "savings", "budgets", "next_period_settings"):
        for key, n in body.get(section, {}).items():
            rows.append({"section": section, "key": key, "value": n["value"], "unit": n["unit"],
                         "provenance": n["provenance"], "source": n["source"],
                         "coverage_permille": n.get("coverage_permille")})
    return rows


def to_csv(rows: list[dict]) -> str:
    out = io.StringIO()
    w = csv.writer(out, lineterminator="\n")
    w.writerow(CSV_COLUMNS)
    for r in rows:
        w.writerow(["" if r[c] is None else r[c] for c in CSV_COLUMNS])
    return out.getvalue()


class ReportService:
    def __init__(self, store, summary: Callable, findings: Callable, budgets: Callable, burn: Callable,
                 audit: Callable | None = None, publish: Callable | None = None,
                 now: Callable[[], datetime] | None = None) -> None:
        self.store, self.summary, self.findings, self.budgets, self.burn = store, summary, findings, budgets, burn
        self.audit_fn, self.publish = audit, publish
        self.now = now or (lambda: datetime.now(timezone.utc))

    def _audit(self, action, actor, detail, ws) -> None:
        if self.audit_fn:
            self.audit_fn(action, actor, detail, workspace_id=ws)

    # -- generate ------------------------------------------------------------------------------------------------
    def generate(self, ws: str, period: dict, actor: str | None = None) -> ReportRow:
        try:
            d_from, d_to = date.fromisoformat(str(period["from"])), date.fromisoformat(str(period["to"]))
        except (KeyError, ValueError, TypeError):
            raise ReportError("invalid_request", "period needs ISO dates from/to", 422) from None
        if d_to < d_from:
            raise ReportError("invalid_request", "period.to before period.from", 422)
        t_from = datetime(d_from.year, d_from.month, d_from.day, tzinfo=timezone.utc)
        t_to = datetime(d_to.year, d_to.month, d_to.day, 23, 59, 59, tzinfo=timezone.utc)
        body = {"period": {"from": d_from.isoformat(), "to": d_to.isoformat()},
                "usage": self._usage(ws, t_from, t_to), "savings": self._savings(ws, t_from, t_to),
                "budgets": self._budgets(ws), "next_period_settings": {}}
        body["next_period_settings"] = self._settings(body)
        row = self.store.add(ReportRow(str(uuid.uuid4()), ws, d_from, d_to, actor, body, self.now()))
        self._audit("report.generate", actor, {"report_id": row.id, "rows": len(flatten(body))}, ws)
        if self.publish:
            self.publish("report.report.generated", {"workspace_id": ws, "report_id": row.id})
        return row

    def _usage(self, ws, t_from, t_to) -> dict:
        tiles = self.summary(ws, t_from, t_to).get("tiles", {})
        keys = ("total_tokens", "cost_list", "cost_cli", "correct_tasks", "cost_list_per_correct",
                "cost_cli_per_correct")
        return {k: _tile(tiles.get(k), "usage.api.summary") for k in keys}

    def _savings(self, ws, t_from, t_to) -> dict:
        out, tot = {}, {"p10": 0, "p50": 0, "p90": 0}
        fs = self.findings(ws, t_from, t_to)
        for f in fs:
            s = f["savings"]
            for q in tot:
                tot[q] += s[q] or 0
                out[f"{f['rule_id']}.{f['id']}.{q}"] = num(s[q], "microusd", s.get("provenance", "ESTIMATED"),
                                                          "advisor.api.list_findings")
        for q, v in tot.items():
            out[f"total.{q}"] = num(v if fs else None, "microusd", "ESTIMATED", "advisor.api.list_findings")
        return out

    def _budgets(self, ws) -> dict:
        out = {}
        for b in self.budgets(ws):
            bid, burn = b["id"], self.burn(ws, b["id"])
            out[f"{bid}.limit"] = num(b["limit_microusd"], "microusd", "CONFIGURED", "quota.api.burn")
            for m, c in burn["cumulative"].items():
                pts = c["points"]
                last = pts[-1][1] if pts else None
                out[f"{bid}.used_{m}"] = num(last, "microusd", c["provenance"], "quota.api.burn")
            for q in ("p10", "p50", "p90"):
                out[f"{bid}.exhaust_at_{q}"] = num(burn["projection"].get(f"exhaust_at_{q}"), "date", "CALCULATED",
                                                  "quota.api.burn")
        return out

    @staticmethod
    def _settings(body) -> dict:
        """Next-period settings: keep today's budget limits; each rule's p50 saving is a candidate headroom cut."""
        out = {}
        for k, n in body["budgets"].items():
            if k.endswith(".limit"):
                out[f"{k[:-6]}.next_limit"] = num(n["value"], "microusd", "CONFIGURED", n["source"])
        out["expected_savings_p50"] = {**body["savings"].get("total.p50", num(None, "microusd", "ESTIMATED",
                                                                              "advisor.api.list_findings"))}
        return out

    # -- read / export -------------------------------------------------------------------------------------------
    def get(self, ws, rid) -> ReportRow:
        r = self.store.get(ws, rid)
        if r is None:
            raise ReportError("not_found", "report not found", 404)
        return r

    def list(self, ws) -> list[ReportRow]:
        return self.store.list(ws)

    def view(self, r: ReportRow) -> dict:
        return {"id": r.id, "period": {"from": r.period_start.isoformat(), "to": r.period_end.isoformat()},
                "body": r.body, "created_at": r.created_at.isoformat()}

    def export(self, ws: str, rid: str, fmt: str, actor: str | None = None) -> tuple[str, str]:
        """-> (content_type, text). Audited: who exported which report in which format."""
        if fmt not in FORMATS:
            raise ReportError("invalid_request", "format must be json or csv", 422)
        r = self.get(ws, rid)
        rows = flatten(r.body)
        self._audit("report.export", actor, {"report_id": r.id, "format": fmt, "rows": len(rows)}, ws)
        if fmt == "csv":
            return "text/csv", to_csv(rows)
        import json
        return "application/json", json.dumps({**self.view(r), "rows": rows}, sort_keys=True)

import csv
import io
import json
import unittest
from datetime import datetime, timezone

from app.domains.report.service import CSV_COLUMNS, MemoryStore, ReportError, ReportService, flatten

WS = "00000000-0000-4000-8000-000000000001"
USER = "00000000-0000-4000-8000-0000000000d1"
NOW = datetime(2026, 10, 10, 12, 0, tzinfo=timezone.utc)
PERIOD = {"from": "2026-10-01", "to": "2026-10-31"}


def summary(ws, frm, to, project=None):
    return {"tiles": {
        "total_tokens": {"value": 5000, "unit": "tokens", "provenance": "MEASURED"},
        "cost_list": {"value": 12000, "unit": "microusd", "provenance": "CALCULATED"},
        "cost_cli": {"value": None, "unit": "microusd", "provenance": "MEASURED", "coverage_permille": 0},
        "correct_tasks": {"value": 3, "unit": "tasks", "provenance": "CALCULATED"},
        "cost_list_per_correct": {"value": 4000, "unit": "microusd", "provenance": "CALCULATED"},
        "cost_cli_per_correct": {"value": None, "unit": "microusd", "provenance": "MEASURED", "coverage_permille": 0}}}


def findings(ws, frm, to):
    return [{"id": "f1", "rule_id": "R1", "savings": {"p10": 100, "p50": 300, "p90": 500, "unit": "microusd",
                                                       "provenance": "ESTIMATED"}},
            {"id": "f2", "rule_id": "R3", "savings": {"p10": 10, "p50": 20, "p90": 30, "unit": "microusd",
                                                       "provenance": "ESTIMATED"}}]


def budgets(ws):
    return [{"id": "b1", "limit_microusd": 50000}]


def burn(ws, bid):
    return {"budget_id": bid, "limit_microusd": 50000,
            "cumulative": {"list": {"provenance": "CALCULATED", "points": [["2026-10-01", 100], ["2026-10-02", 250]]},
                           "cli": {"provenance": "MEASURED", "points": []}},
            "projection": {"exhaust_at_p10": None, "exhaust_at_p50": "2026-10-28T00:00:00Z",
                           "exhaust_at_p90": "2026-10-20T00:00:00Z"}}


def make(**over):
    audit, events = [], []
    kw = dict(summary=summary, findings=findings, budgets=budgets, burn=burn,
              audit=lambda a, actor, d, **k: audit.append((a, actor, d)),
              publish=lambda n, p: events.append(n), now=lambda: NOW)
    kw.update(over)
    return ReportService(MemoryStore(), **kw), audit, events


class ReportTest(unittest.TestCase):
    def test_csv_and_json_exports_agree(self):
        s, _, _ = make()
        r = s.generate(WS, PERIOD, USER)
        _, js = s.export(WS, r.id, "json", USER)
        _, cs = s.export(WS, r.id, "csv", USER)
        jrows = json.loads(js)["rows"]
        crows = list(csv.DictReader(io.StringIO(cs)))
        self.assertEqual(len(jrows), len(crows))
        self.assertGreater(len(crows), 10)
        for j, c in zip(jrows, crows):
            for col in CSV_COLUMNS:
                self.assertEqual("" if j[col] is None else str(j[col]), c[col])

    def test_every_number_has_provenance_and_source(self):
        s, _, _ = make()
        r = s.generate(WS, PERIOD)
        for sec in ("usage", "savings", "budgets", "next_period_settings"):
            self.assertTrue(r.body[sec], sec)
            for k, n in r.body[sec].items():
                self.assertTrue(n["provenance"], k)
                self.assertTrue(n["source"], k)
        _, cs = s.export(WS, r.id, "csv")
        for c in csv.DictReader(io.StringIO(cs)):
            self.assertTrue(c["provenance"] and c["source"], c)

    def test_both_cost_measures_side_by_side_and_unknown_stays_null(self):
        s, _, _ = make()
        u = s.generate(WS, PERIOD).body["usage"]
        self.assertEqual(u["cost_list"]["value"], 12000)
        self.assertIsNone(u["cost_cli"]["value"])
        self.assertEqual(u["cost_cli"]["provenance"], "MEASURED")
        self.assertEqual(u["cost_cli"]["coverage_permille"], 0)

    def test_savings_are_estimated_percentiles_with_total(self):
        sv = make()[0].generate(WS, PERIOD).body["savings"]
        self.assertEqual(sv["total.p50"]["value"], 320)
        self.assertEqual(sv["R1.f1.p90"]["provenance"], "ESTIMATED")

    def test_budget_status_and_next_period_settings(self):
        b = make()[0].generate(WS, PERIOD).body
        self.assertEqual(b["budgets"]["b1.used_list"]["value"], 250)
        self.assertIsNone(b["budgets"]["b1.used_cli"]["value"])
        self.assertEqual(b["budgets"]["b1.exhaust_at_p50"]["value"], "2026-10-28T00:00:00Z")
        self.assertEqual(b["next_period_settings"]["b1.next_limit"]["value"], 50000)
        self.assertEqual(b["next_period_settings"]["expected_savings_p50"]["value"], 320)

    def test_export_is_audited_with_ids_only(self):
        s, audit, _ = make()
        r = s.generate(WS, PERIOD, USER)
        audit.clear()
        s.export(WS, r.id, "csv", USER)
        self.assertEqual(audit, [("report.export", USER, {"report_id": r.id, "format": "csv",
                                                           "rows": len(flatten(r.body))})])

    def test_failed_export_is_not_audited_and_bad_input_rejected(self):
        s, audit, _ = make()
        r = s.generate(WS, PERIOD)
        audit.clear()
        for args in ((WS, r.id, "pdf"), ("other-ws", r.id, "csv"), (WS, "nope", "json")):
            with self.assertRaises(ReportError):
                s.export(*args)
        self.assertEqual(audit, [])

    def test_generate_validates_period_audits_and_publishes(self):
        s, audit, events = make()
        for bad in ({}, {"from": "x", "to": "2026-10-01"}, {"from": "2026-10-05", "to": "2026-10-01"}):
            with self.assertRaises(ReportError) as c:
                s.generate(WS, bad)
            self.assertEqual(c.exception.status, 422)
        s.generate(WS, PERIOD, USER)
        self.assertEqual([a for a, _, _ in audit], ["report.generate"])
        self.assertEqual(events, ["report.report.generated"])

    def test_workspace_isolation_and_list(self):
        s, _, _ = make()
        r = s.generate(WS, PERIOD)
        self.assertEqual([x.id for x in s.list(WS)], [r.id])
        self.assertEqual(s.list("other"), [])

    def test_no_budgets_no_findings_gives_null_totals_not_zero(self):
        s, _, _ = make(findings=lambda *a: [], budgets=lambda ws: [])
        b = s.generate(WS, PERIOD).body
        self.assertIsNone(b["savings"]["total.p50"]["value"])
        self.assertEqual(b["budgets"], {})


if __name__ == "__main__":
    unittest.main()

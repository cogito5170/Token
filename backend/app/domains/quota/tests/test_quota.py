import unittest
from datetime import datetime, timedelta, timezone

from app.domains.quota.service import MemoryStore, QuotaError, QuotaService

WS = "00000000-0000-4000-8000-000000000001"
NOW = datetime(2026, 10, 10, 12, 0, tzinfo=timezone.utc)


def fake_summary(days, cov=1000):
    """days: list of (list_cost, cli_cost|None) per day starting at the period's first day."""
    def summary(ws, frm, to, project=None):
        pts = lambda i: [[(frm + timedelta(days=n)).isoformat(), d[i]] for n, d in enumerate(days)]  # noqa: E731
        cli = [d[1] for d in days if d[1] is not None]
        return {"tiles": {"cost_list": {"value": sum(d[0] for d in days)},
                          "cost_cli": {"value": sum(cli) if cli else None, "coverage_permille": cov}},
                "trend": {"series": [{"name": "cost_list", "points": pts(0)}, {"name": "cost_cli", "points": pts(1)}]}}
    return summary


def svc(days, cov=1000, **kw):
    return QuotaService(MemoryStore(), fake_summary(days, cov), now=lambda: NOW, **kw)


class QuotaTest(unittest.TestCase):
    def test_used_returns_both_measures_and_cli_coverage(self):
        s = svc([(100, 80), (100, None)], cov=500)
        b = s.create(WS, None, "workspace", "month", "list", 10_000)
        used = s.view(b)["used"]
        self.assertEqual(used["list"]["value"], 200)
        self.assertEqual(used["cli"]["value"], 80)
        self.assertLess(used["cli"]["coverage_permille"], 1000)
        self.assertEqual(used["list"]["provenance"], "CALCULATED")
        self.assertEqual(used["cli"]["provenance"], "MEASURED")

    def test_cli_unknown_is_null_not_zero(self):
        s = svc([(100, None)], cov=0)
        b = s.create(WS, None, "workspace", "month", "cli", 1000)
        self.assertIsNone(s.view(b)["used"]["cli"]["value"])
        self.assertEqual(s.evaluate(WS), [])

    def test_alert_80_once_per_period(self):
        s = svc([(850, 850)])
        s.create(WS, None, "workspace", "month", "list", 1000)
        first = s.evaluate(WS)
        self.assertEqual([a.threshold for a in first], [50, 80])
        self.assertEqual(s.evaluate(WS), [])
        self.assertEqual([a["threshold"] for a in s.alerts(WS)].count(80), 1)

    def test_alert_again_next_period(self):
        s = svc([(850, 850)])
        s.create(WS, None, "workspace", "month", "list", 1000)
        s.evaluate(WS)
        s.now = lambda: datetime(2026, 11, 3, tzinfo=timezone.utc)
        self.assertEqual([a.threshold for a in s.evaluate(WS)], [50, 80])

    def test_notify_called_once_per_alert(self):
        seen = []
        s = svc([(1000, 1000)], notify=lambda b, a: seen.append(a.threshold))
        s.create(WS, None, "workspace", "month", "list", 1000)
        s.evaluate(WS)
        s.evaluate(WS)
        self.assertEqual(seen, [50, 80, 100])

    def test_check_blocks_over_limit(self):
        s = svc([(900, 0)])
        s.create(WS, None, "workspace", "month", "list", 1000)
        self.assertTrue(s.check(WS, "workspace", 100)["allowed"])
        r = s.check(WS, "workspace", 101)
        self.assertFalse(r["allowed"])
        self.assertEqual(r["blocked_by"][0]["after_microusd"], 1001)

    def test_check_cli_budget_uses_cli_extra(self):
        s = svc([(10, 900)])
        s.create(WS, None, "workspace", "month", "cli", 1000)
        self.assertFalse(s.check(WS, "workspace", 5, cost_cli=200)["allowed"])
        self.assertTrue(s.check(WS, "workspace", 5, cost_cli=50)["allowed"])

    def test_check_scope_and_archive(self):
        s = svc([(900, 0)])
        b = s.create(WS, None, "project", "month", "list", 1000, project_id="p1")
        self.assertTrue(s.check(WS, "workspace", 10**6)["allowed"])
        self.assertTrue(s.check(WS, "project", 10**6, "p2")["allowed"])
        self.assertFalse(s.check(WS, "project", 200, "p1")["allowed"])
        s.archive(WS, b.id)
        self.assertTrue(s.check(WS, "project", 10**6, "p1")["allowed"])

    def test_burn_projection_and_exhaustion(self):
        s = svc([(100, 50)] * 10)
        b = s.create(WS, None, "workspace", "month", "list", 1500)
        r = s.burn(WS, b.id)
        self.assertEqual(r["cumulative"]["list"]["points"][-1][1], 1000)
        self.assertEqual(r["cumulative"]["cli"]["points"][-1][1], 500)
        self.assertEqual(r["projection"]["p50"]["points"][0][1], 1100)
        self.assertEqual(r["projection"]["exhaust_at_p50"], "2026-10-15T00:00:00Z")
        self.assertEqual(r["projection"]["exhaust_at_p10"], r["projection"]["exhaust_at_p90"])

    def test_burn_band_orders(self):
        s = svc([(10, 0), (300, 0), (50, 0), (100, 0), (20, 0)])
        b = s.create(WS, None, "workspace", "month", "list", 2000)
        p = s.burn(WS, b.id)["projection"]
        self.assertLessEqual(p["p10"]["points"][-1][1], p["p50"]["points"][-1][1])
        self.assertLessEqual(p["p50"]["points"][-1][1], p["p90"]["points"][-1][1])

    def test_validation(self):
        s = svc([])
        for kw in ({"scope": "x"}, {"measure": "usd"}, {"limit_microusd": 0}, {"scope": "project"},
                   {"thresholds": [0]}):
            args = dict(scope="workspace", period="month", measure="list", limit_microusd=5)
            args.update(kw)
            with self.assertRaises(QuotaError):
                s.create(WS, None, **args)

    def test_workspace_isolation(self):
        s = svc([(1, 1)])
        b = s.create(WS, None, "workspace", "month", "list", 5)
        with self.assertRaises(QuotaError):
            s.get("other", b.id)

    def test_create_audited(self):
        calls = []
        s = svc([], audit=lambda *a, **k: calls.append(a[0]))
        s.create(WS, "u", "workspace", "month", "list", 5)
        self.assertEqual(calls, ["budget.create"])


if __name__ == "__main__":
    unittest.main()

"""Acceptance test for CMD-TKG14 (written by baseline; the executor may not edit it)."""
import unittest
from datetime import datetime, timezone

from app.domains.quota.service import MemoryStore, QuotaError, QuotaService


class T(unittest.TestCase):
    def test_negative_cost_cli_rejected(self):
        s = {"tiles": {"cost_list": {"value": 0}, "cost_cli": {"value": 100, "coverage_permille": 1000}},
             "trend": {"series": []}}
        svc = QuotaService(MemoryStore(), summary=lambda *a: s, now=lambda: datetime(2026, 10, 6, tzinfo=timezone.utc))
        svc.create("w", None, "workspace", "month", "cli", 150)
        for bad in (-1000, "5", True):
            with self.assertRaises(QuotaError, msg=repr(bad)):
                svc.check("w", "workspace", 200, cost_cli=bad)

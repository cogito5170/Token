"""Acceptance test for CMD-TKG8 (written by baseline; the executor may not edit it)."""
import unittest
from datetime import datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))

from app.domains.usage.service import MemoryStore, UsageService


class SummaryPeriodIsUtc(unittest.TestCase):
    def svc(self):
        return UsageService(MemoryStore(), now=lambda: datetime(2026, 9, 3, tzinfo=timezone.utc))

    def test_period_is_the_queried_utc_dates(self):
        r = self.svc().summary("w", datetime(2026, 9, 1, 0, 30, tzinfo=KST), datetime(2026, 9, 2, 0, 30, tzinfo=KST))
        self.assertEqual(r["period"], {"from": "2026-08-31", "to": "2026-09-01"})

    def test_utc_input_unchanged(self):
        r = self.svc().summary("w", datetime(2026, 9, 1, tzinfo=timezone.utc), datetime(2026, 9, 2, tzinfo=timezone.utc))
        self.assertEqual(r["period"], {"from": "2026-09-01", "to": "2026-09-02"})

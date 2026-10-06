"""Acceptance test for CMD-TKG7 (written by baseline; the executor may not edit it)."""
import unittest
from datetime import datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))

from app.domains.estimation.service import EstimationService


def oc(ape):
    return {"total_tokens": {"ape_permille": ape, "within_p10_p90": True}}


class AccuracyDaysAreUtc(unittest.TestCase):
    def test_days_are_utc_dates(self):
        svc = EstimationService(prior=[])
        svc.store.outcomes_ = {
            "a": {"at": datetime(2026, 9, 2, 3, 0, tzinfo=KST), "workspace_id": "w", "oc": oc(100)},
            "b": {"at": datetime(2026, 9, 1, 23, 0, tzinfo=timezone.utc), "workspace_id": "w", "oc": oc(300)},
            "c": {"at": datetime(2026, 9, 2, 1, 0), "workspace_id": "w", "oc": oc(50)},
        }
        pts = svc.accuracy_view("w")["series"]["series"][0]["points"]
        self.assertEqual(pts, [["2026-09-01T00:00:00Z", 200], ["2026-09-02T00:00:00Z", 50]])

"""Acceptance test for CMD-TKG13 (written by baseline; the executor may not edit it)."""
import unittest
from app.domains.quota.service import MemoryStore, QuotaError, QuotaService


class T(unittest.TestCase):
    def test_bool_limit_and_threshold_rejected(self):
        svc = QuotaService(MemoryStore(), summary=lambda *a: {})
        with self.assertRaises(QuotaError):
            svc.create("w", None, "workspace", "month", "list", True)
        with self.assertRaises(QuotaError):
            svc.create("w", None, "workspace", "month", "list", 1000, thresholds=[True])

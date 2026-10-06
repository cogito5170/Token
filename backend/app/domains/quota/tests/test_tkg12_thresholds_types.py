"""Acceptance test for CMD-TKG12 (written by baseline; the executor may not edit it)."""
import unittest
from app.domains.quota.service import MemoryStore, QuotaError, QuotaService


class T(unittest.TestCase):
    def test_mixed_type_thresholds_rejected(self):
        svc = QuotaService(MemoryStore(), summary=lambda *a: {})
        for th in ([50, "80"], [[1]], [None, 5]):
            with self.assertRaises(QuotaError, msg=repr(th)):
                svc.create("w", None, "workspace", "month", "list", 1000, thresholds=th)

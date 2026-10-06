"""Acceptance test for CMD-TKG19 (written by baseline; the executor may not edit it)."""
import unittest
from app.domains.report.service import MemoryStore, ReportError, ReportService


class T(unittest.TestCase):
    def test_non_dict_period_rejected(self):
        svc = ReportService(MemoryStore(), lambda *a: {}, lambda *a: [], lambda ws: [], lambda ws, b: {})
        for p in (None, [], "2026-01-01", 5):
            with self.assertRaises(ReportError, msg=repr(p)):
                svc.generate("w", p)

"""Acceptance test for CMD-TKG6 (written by baseline; the executor may not edit it)."""
import math
import unittest

from app.domains.run.gadir import _permille


class PermilleNeverRaises(unittest.TestCase):
    def test_infinities_clamp(self):
        self.assertEqual(_permille(math.inf), 1000)
        self.assertEqual(_permille("inf"), 1000)
        self.assertEqual(_permille(-math.inf), 0)
        self.assertEqual(_permille(math.nan), 0)

    def test_existing_behaviour(self):
        for v, want in ((0.5, 500), (2, 1000), (-1, 0), (None, 0), ("x", 0), ("0.25", 250)):
            self.assertEqual(_permille(v), want, v)

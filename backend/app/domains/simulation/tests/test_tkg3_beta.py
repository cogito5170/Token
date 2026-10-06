"""Acceptance test for CMD-TKG3 (written by baseline; the executor may not edit it)."""
import math
import unittest

from app.domains.simulation.service import beta_quantiles_permille as bq


class BetaLaplace(unittest.TestCase):
    def test_p50_is_the_laplace_mean(self):
        self.assertEqual(bq(10, 10)[1], 917)
        self.assertEqual(bq(5, 10)[1], 500)
        self.assertEqual(bq(0, 0)[1], 500)
        self.assertEqual(bq(0, 10)[1], 83)

    def test_all_successes_is_not_certain(self):
        p10, p50, p90 = bq(10, 10)
        self.assertLess(p10, p50)
        self.assertLess(p50, 1000)

    def test_order_and_range(self):
        for s, n in ((0, 1), (3, 4), (300, 400), (7, 7)):
            p10, p50, p90 = bq(s, n)
            self.assertTrue(0 <= p10 <= p50 <= p90 <= 1000, (s, n))

import json
import subprocess
import sys
import unittest
from pathlib import Path

from app.domains.estimation.estimator import Evidence, estimate, weighted_quantile
from app.domains.estimation.features import Features, distance, featurize
from app.domains.estimation.outcomes import accuracy, outcome
from app.domains.estimation.prior import load_global_prior
from app.domains.estimation.service import EstimationService

ROOT = Path(__file__).resolve().parents[5]


def ev(i, tokens, kind="k", mode="selective", correct=True, source="user"):
    return Evidence(id=str(i), features=Features(kind, "m", "A", mode), correct=correct, seq=i, source=source,
                    values={"total_tokens": tokens, "calls": 3})


class Backtest(unittest.TestCase):
    def test_beats_baseline_with_coverage(self):
        p = subprocess.run([sys.executable, "scripts/backtest_estimator.py", "--estimator", "app"], cwd=ROOT,
                           capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        res = json.loads(p.stdout.strip().splitlines()[-1])
        self.assertEqual(res["baseline"]["tokens"]["mape_pct"], 21.98)
        self.assertLess(res["app"]["tokens"]["mape_pct"], res["baseline"]["tokens"]["mape_pct"])
        self.assertGreaterEqual(res["app"]["tokens"]["coverage_p10_p90_pct"], 70.0)
        for k in ("cost_microusd", "cost_cli_microusd"):
            self.assertIn(k, res["app"])


class NoLeakage(unittest.TestCase):
    def test_run_never_in_its_own_evidence(self):
        import importlib.util
        from unittest import mock

        import app.domains.estimation.estimator as est
        spec = importlib.util.spec_from_file_location("backtest_estimator", ROOT / "scripts" / "backtest_estimator.py")
        bt = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(bt)
        rows = bt.load(bt.RUNS)
        seen = []
        real = est.estimate

        def spy(target, user_pool, global_pool, *a, **k):
            seen.append([e.id for e in user_pool + global_pool])
            return real(target, user_pool, global_pool, *a, **k)

        with mock.patch.object(est, "estimate", spy):
            bt.app_scorer(rows)
        self.assertEqual(len(seen), len(rows))
        for r, ids in zip(rows, seen):
            self.assertNotIn(r["run_id"], ids)
            self.assertEqual(len(ids), len(rows) - 1)


class Rules(unittest.TestCase):
    def test_few_evidence_widens(self):
        pool = [ev(1, 1000), ev(2, 1000)]
        e = estimate(Features("k", "m", "A"), [], pool)
        self.assertTrue(e.widened)
        self.assertEqual(e.ranges["total_tokens"], {"p10": 500, "p50": 1000, "p90": 2000})
        self.assertEqual(e.evidence_n, 2)

    def test_enough_evidence_not_widened(self):
        e = estimate(Features("k", "m", "A"), [], [ev(i, 1000) for i in range(3)])
        self.assertFalse(e.widened)
        self.assertEqual(e.ranges["total_tokens"], {"p10": 1000, "p50": 1000, "p90": 1000})

    def test_context_mode_dominates_distance(self):
        a = Features("k", "m", "A", "bulk")
        self.assertGreater(distance(a, Features("k", "m", "A", "selective")), distance(a, Features("j", "m", "A", "bulk")))
        self.assertEqual(distance(a, a), 0)

    def test_weighted_quantile_monotone(self):
        pairs = [(10, 1.0), (20, 1.0), (1000, 0.1)]
        q = [weighted_quantile(pairs, x) for x in (0.1, 0.5, 0.9)]
        self.assertEqual(q, sorted(q))
        self.assertLess(q[1], 100)

    def test_laplace_success(self):
        e = estimate(Features("k", "m", "A"), [], [ev(i, 100, correct=True) for i in range(4)])
        self.assertEqual(e.success_permille, 1000 * 5 // 6)  # (4+1)/(4+2)
        e0 = estimate(Features("k", "m", "A"), [], [ev(i, 100, correct=False) for i in range(4)])
        self.assertEqual(e0.success_permille, 167)

    def test_user_blend(self):
        user = [ev(i, 2000) for i in range(10)]
        glob = [ev(100 + i, 1000, source="global") for i in range(5)]
        e = estimate(Features("k", "m", "A"), user, glob)
        self.assertEqual(e.basis, "blended")
        self.assertEqual(e.ranges["total_tokens"]["p50"], 1500)  # lambda = 10/20
        self.assertEqual(estimate(Features("k", "m", "A"), user, []).basis, "user")
        self.assertEqual(estimate(Features("k", "m", "A"), [], glob).basis, "global_prior")

    def test_k_limit(self):
        e = estimate(Features("k", "m", "A"), [], [ev(i, 100) for i in range(40)])
        self.assertEqual(e.evidence_n, 15)

    def test_outcome_and_accuracy(self):
        o = outcome({"total_tokens": {"p10": 80, "p50": 90, "p90": 120}}, {"total_tokens": 100})
        self.assertEqual(o["total_tokens"], {"actual": 100, "ape_permille": 100, "within_p10_p90": True})
        o2 = outcome({"total_tokens": {"p10": 80, "p50": 90, "p90": 120}}, {"total_tokens": 200})
        self.assertFalse(o2["total_tokens"]["within_p10_p90"])
        self.assertEqual(accuracy([o, o2], "total_tokens"), {"n": 2, "mape_permille": 325, "coverage_permille": 500})

    def test_prior_excludes_void(self):
        n = len(load_global_prior())
        self.assertEqual(n, 100)


class NoDescriptionStored(unittest.TestCase):
    SECRET = "refactor the payroll module quietly"

    def test_featurize_drops_text(self):
        f, stored = featurize({"task_kind": "k", "model": "m", "description": self.SECRET})
        self.assertNotIn(self.SECRET, json.dumps(stored))
        self.assertEqual(stored["description"]["len"], len(self.SECRET))
        self.assertEqual(len(stored["description"]["sha256"]), 64)
        self.assertEqual(f.description_len, len(self.SECRET))

    def test_service_row_has_no_text(self):
        svc = EstimationService(prior=[ev(i, 100, source="global") for i in range(5)])
        row = svc.create("w", {"task_kind": "k", "model": "m", "description": self.SECRET})
        self.assertNotIn(self.SECRET, json.dumps(row))
        self.assertEqual(row["provenance"], "ESTIMATED")
        self.assertEqual(row["evidence"]["n"], 5)
        svc.record_outcome(row["id"], {"total_tokens": 100})
        self.assertEqual(svc.accuracy()["mape_permille"], 0)

    def test_unknown_outcome_tasks_are_not_evidence(self):
        tasks = [{"id": "t1", "kind": "k", "model": "m", "outcome": "unknown", "total_tokens": 5}]
        svc = EstimationService(lambda ws: tasks, prior=[ev(i, 100, source="global") for i in range(5)])
        self.assertEqual(svc.create("w", {"task_kind": "k", "model": "m"})["evidence"]["basis"], "global_prior")


if __name__ == "__main__":
    unittest.main()

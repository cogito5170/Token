import unittest
from datetime import datetime, timedelta, timezone

from app.domains.simulation.service import (SimulationError, SimulationService, beta_quantiles_permille, validate)
from app.domains.simulation.store import MemoryStore

WS, USER = "00000000-0000-4000-8000-000000000001", "00000000-0000-4000-8000-0000000000aa"
T0 = datetime(2026, 3, 1, 12, 0, tzinfo=timezone.utc)
BASIS = {"from": "2026-03-01T00:00:00Z", "to": "2026-03-31T00:00:00Z"}
PRICES = {"big": {"version": 3, "in": 5_000_000, "out": 25_000_000, "cr": 500_000, "cw5": 6_250_000},
          "small": {"version": 2, "in": 1_000_000, "out": 5_000_000, "cr": 100_000, "cw5": 1_250_000},
          "twin": {"version": 7, "in": 5_000_000, "out": 25_000_000, "cr": 500_000, "cw5": 6_250_000}}


def nano(p, i, cr, cw, o):
    return (i * p["in"] + cr * p["cr"] + cw * p["cw5"] + o * p["out"]) // 1000


def call(i, model="big", ctx=None, inp=10_000, cr=0, cw=0, out=500, session="s1", task="t1", secs=0):
    ctx = ctx if ctx is not None else inp + cr + cw
    return {"id": i, "occurred_at": (T0 + timedelta(seconds=secs)).isoformat().replace("+00:00", "Z"), "model_id": model,
            "session_id": session, "task_id": task, "input_tokens": inp, "cache_read_tokens": cr,
            "cache_write_tokens": cw, "output_tokens": out, "context_tokens": ctx,
            "cost_list_microusd": nano(PRICES[model], inp, cr, cw, out) // 1000}


def stat(model, kind="feature", structure="single", tasks=10, correct=9, tpc=100_000, cost=500_000):
    m = lambda v, u: {"value": v, "unit": u, "provenance": "CALCULATED"}  # noqa: E731
    return {"task_kind": kind, "model_id": model, "structure": structure, "context_mode": "selective", "tasks": tasks,
            "correct": correct, "tokens_per_correct": m(tpc, "tokens"), "cost_list_per_correct": m(cost, "microusd"),
            "version": 4}


def make(calls, tasks=None, stats=None, prices=None, proposer=None, ctxbudget=None):
    tasks = tasks if tasks is not None else [{"id": "t1", "kind": "feature", "structure": "single"}]
    events = []
    svc = SimulationService(MemoryStore(), lambda *a: calls, lambda *a: tasks, lambda *a: stats or [],
                            lambda: prices or PRICES, proposer, lambda n, p: events.append((n, p)),
                            ctxbudget=ctxbudget or (lambda *a: None), now=lambda: T0)
    svc.events = events
    return svc


def sim(svc, *assumptions):
    return svc.simulate(WS, USER, list(assumptions), BASIS)


class ValidationTest(unittest.TestCase):
    def test_empty_or_missing_assumptions_are_422(self):
        for bad in ([], None, "x", {}):
            with self.assertRaises(SimulationError) as e:
                make([call(1)]).simulate(WS, USER, bad, BASIS)
            self.assertEqual(e.exception.status, 422)

    def test_bad_assumptions_and_basis_are_422(self):
        bad = [{"kind": "nope", "value": 1}, {"kind": "context_cap", "value": 0}, {"kind": "context_cap", "value": "9"},
               {"kind": "model_swap", "value": "small"}, {"kind": "structure", "value": "Z"},
               {"kind": "node_count", "value": 2, "from": 0}, "model_swap"]
        for a in bad:
            with self.assertRaises(SimulationError, msg=a) as e:
                validate([a], BASIS)
            self.assertEqual(e.exception.status, 422)
        for b in (None, {"from": BASIS["from"]}, {"from": "x", "to": BASIS["to"]},
                  {"from": BASIS["to"], "to": BASIS["from"]}):
            with self.assertRaises(SimulationError):
                validate([{"kind": "cache_prefix_fixed", "value": {}}], b)

    def test_nothing_is_saved_when_validation_fails(self):
        svc = make([call(1)])
        with self.assertRaises(SimulationError):
            svc.simulate(WS, USER, [], BASIS)
        self.assertEqual((svc.store.rows, svc.events), ({}, []))


class ProvenanceTest(unittest.TestCase):
    ALL = [{"kind": "model_swap", "from": "big", "value": "small"}, {"kind": "context_cap", "value": 4000},
           {"kind": "node_count", "value": 2}, {"kind": "cache_prefix_fixed", "value": {}},
           {"kind": "structure", "value": "B"}]

    def test_every_kind_is_simulated_with_basis_and_price_version(self):
        calls = [call(1, ctx=30_000, inp=30_000), call(2, inp=8000, secs=10), call(3, inp=8000, secs=20)]
        for a in self.ALL:
            s = sim(make(calls), a)
            self.assertEqual(s["provenance"], "SIMULATED", a)
            self.assertEqual(s["assumptions"][0]["kind"], a["kind"])
            for k in ("from", "to", "calls", "tasks", "price_version", "stats_version"):
                self.assertIn(k, s["basis"], a)
            self.assertIsInstance(s["basis"]["price_version"], int)
            self.assertEqual((s["basis"]["calls"], s["basis"]["tasks"]), (3, 1))
            for name, r in s["result"]["simulated"].items():
                self.assertEqual(r["provenance"], "SIMULATED", (a, name))
                self.assertLessEqual(r["p10"], r["p50"])
                self.assertLessEqual(r["p50"], r["p90"])
                self.assertTrue(all(isinstance(r[q], int) for q in ("p10", "p50", "p90")))
            self.assertEqual(s["result"]["baseline"]["cost_list_microusd"]["provenance"], "CALCULATED")

    def test_price_version_is_the_newest_of_models_used_including_swap_target(self):
        s = sim(make([call(1, "small")]), {"kind": "model_swap", "from": "small", "value": "big"})
        self.assertEqual(s["basis"]["price_version"], 3)
        s = sim(make([call(1, "small")]), {"kind": "context_cap", "value": 100})
        self.assertEqual(s["basis"]["price_version"], 2)

    def test_stored_result_round_trips_and_event_published(self):
        svc = make([call(1)])
        s = sim(svc, {"kind": "context_cap", "value": 4000})
        self.assertEqual(svc.get(WS, s["id"]), s)
        self.assertEqual(svc.events, [("simulation.simulation.completed", {"workspace_id": WS, "simulation_id": s["id"]})])
        with self.assertRaises(SimulationError) as e:
            svc.get(WS, "missing")
        self.assertEqual(e.exception.status, 404)
        with self.assertRaises(SimulationError):
            svc.get("other-ws", s["id"])

    def test_no_prices_is_503(self):
        svc = make([call(1)])
        svc.prices_fn = lambda: {}
        with self.assertRaises(SimulationError) as e:
            sim(svc, {"kind": "context_cap", "value": 1})
        self.assertEqual(e.exception.status, 503)


class ModelSwapTest(unittest.TestCase):
    def test_identical_prices_change_cost_by_zero(self):
        calls = [call(1, inp=12_345, out=777, cr=300), call(2, inp=999, out=3)]
        s = sim(make(calls), {"kind": "model_swap", "from": "big", "value": "twin"})
        base = s["result"]["baseline"]["cost_list_microusd"]["value"]
        self.assertGreater(base, 0)
        r = s["result"]["simulated"]
        self.assertEqual((r["cost_list_microusd"]["p10"], r["cost_list_microusd"]["p50"],
                          r["cost_list_microusd"]["p90"]), (base, base, base))
        self.assertEqual((r["saving_microusd"]["p10"], r["saving_microusd"]["p50"], r["saving_microusd"]["p90"]), (0, 0, 0))

    def test_cheaper_model_lowers_cost_by_the_price_ratio(self):
        s = sim(make([call(1, inp=1_000_000, out=0)]), {"kind": "model_swap", "from": "big", "value": "small"})
        self.assertEqual(s["result"]["baseline"]["cost_list_microusd"]["value"], 5_000_000)
        self.assertEqual(s["result"]["simulated"]["cost_list_microusd"]["p50"], 1_000_000)

    def test_only_calls_of_the_from_model_change(self):
        s = sim(make([call(1, "small", inp=1_000_000, out=0)]), {"kind": "model_swap", "from": "big", "value": "twin"})
        self.assertEqual(s["result"]["simulated"]["saving_microusd"]["p50"], 0)

    def test_token_ratio_from_personal_stats_scales_cost_and_widens_range(self):
        stats = [stat("big", tpc=100_000), stat("small", tpc=200_000, correct=8)]
        s = sim(make([call(1, inp=1_000_000, out=0)], stats=stats), {"kind": "model_swap", "from": "big", "value": "small"})
        c = s["result"]["simulated"]["cost_list_microusd"]
        self.assertEqual(c["p50"], 2_000_000)           # 2x tokens at 1/5 price... = 1M x 2 x $1
        self.assertLess(c["p10"], c["p50"])
        self.assertGreater(c["p90"], c["p50"])
        self.assertEqual(s["result"]["assumptions_applied"][0]["token_ratio_basis"], "personal_stats")
        self.assertEqual(s["basis"]["stats_version"], 4)
        d = s["result"]["simulated"]["success_delta_permille"]
        self.assertLessEqual(d["p10"], d["p50"])
        self.assertLessEqual(d["p50"], d["p90"])

    def test_unknown_target_model_is_422(self):
        with self.assertRaises(SimulationError) as e:
            sim(make([call(1)]), {"kind": "model_swap", "from": "big", "value": "ghost"})
        self.assertEqual(e.exception.status, 422)

    def test_beta_range_is_wider_with_less_evidence_and_ordered(self):
        thin, thick = beta_quantiles_permille(3, 4), beta_quantiles_permille(300, 400)
        self.assertGreater(thin[2] - thin[0], thick[2] - thick[0])
        self.assertTrue(thin[0] <= thin[1] <= thin[2])


class ContextCapTest(unittest.TestCase):
    def test_cap_shrinks_only_calls_above_it(self):
        s = sim(make([call(1, inp=100_000, out=0), call(2, inp=1000, out=0)]), {"kind": "context_cap", "value": 20_000})
        base = s["result"]["baseline"]["cost_list_microusd"]["value"]
        self.assertEqual(s["result"]["simulated"]["cost_list_microusd"]["p50"], base - 400_000)  # 100k -> 20k at $5/M
        self.assertEqual(s["result"]["simulated"]["success_delta_permille"]["p10"], -200)

    def test_cap_above_every_context_changes_nothing(self):
        s = sim(make([call(1, inp=1000)]), {"kind": "context_cap", "value": 20_000})
        self.assertEqual(s["result"]["simulated"]["saving_microusd"]["p50"], 0)

    def test_session_level_ctxbudget_is_reused_and_widens_the_low_side(self):
        seen = []

        def fake(contexts, soft, hard, reset_to):
            seen.append((list(contexts), soft, hard, reset_to))
            return {"saved_pct": 50}
        calls = [call(1, inp=30_000, out=0), call(2, inp=30_000, out=0, secs=5)]
        s = sim(make(calls, ctxbudget=fake), {"kind": "context_cap", "value": 10_000})
        self.assertEqual(len(seen), 1)
        self.assertEqual(seen[0][1], 10_000)
        self.assertEqual(s["result"]["assumptions_applied"][0]["ctxbudget"], "used")
        c = s["result"]["simulated"]["cost_list_microusd"]
        self.assertLessEqual(c["p10"], c["p50"])
        self.assertLess(c["p90"], 300_000 + 1)

    def test_unavailable_ctxbudget_is_recorded_not_fatal(self):
        svc = make([call(1, inp=30_000)])
        svc.ctxbudget = None
        import app.domains.simulation.service as m
        orig, m._default_ctxbudget = m._default_ctxbudget, lambda: None
        try:
            s = sim(svc, {"kind": "context_cap", "value": 10_000})
        finally:
            m._default_ctxbudget = orig
        self.assertIn("unavailable", s["result"]["assumptions_applied"][0]["ctxbudget"])


class NodeCacheStructureTest(unittest.TestCase):
    def test_node_count_scales_linearly(self):
        calls = [call(1, inp=1_000_000, out=0, task="t1"), call(2, inp=1_000_000, out=0, task="t2")]
        tasks = [{"id": "t1", "kind": "feature", "structure": "A"}, {"id": "t2", "kind": "feature", "structure": "A"}]
        s = sim(make(calls, tasks), {"kind": "node_count", "value": 6, "from": 3})
        self.assertEqual(s["result"]["simulated"]["cost_list_microusd"]["p50"], 20_000_000)
        s = sim(make(calls, tasks), {"kind": "node_count", "value": 3, "from": 3})
        self.assertEqual(s["result"]["simulated"]["saving_microusd"]["p50"], 0)

    def test_cache_prefix_uses_r3_fractions_and_never_reports_a_loss(self):
        calls = [call(1, inp=10_000, out=0), call(2, inp=10_000, out=0, secs=60), call(3, inp=10_000, out=0, secs=120)]
        s = sim(make(calls), {"kind": "cache_prefix_fixed", "value": {}})
        sav = s["result"]["simulated"]["saving_microusd"]
        # p50 s=0.5: reads 2 x 0.5 x 10k x (5-0.5) - write premium 0.5 x 10k x (6.25-5) = 45000-6250 /1e3... micro-USD
        self.assertEqual(sav["p50"], (2 * 500 * 10_000 * 4_500_000 - 500 * 10_000 * 1_250_000) // 1000 // 1000 // 1000)
        self.assertLess(sav["p10"], sav["p90"])
        far = [call(1, inp=10_000, out=0), call(2, inp=10_000, out=0, secs=3600)]
        self.assertEqual(sim(make(far), {"kind": "cache_prefix_fixed", "value": {}})["result"]["simulated"]
                         ["saving_microusd"]["p50"], 0)

    def test_structure_uses_cost_per_correct_ratio_and_ignores_missing_stats(self):
        tasks = [{"id": "t1", "kind": "feature", "structure": "A"}]
        stats = [stat("big", structure="A", cost=1_000_000), stat("big", structure="B", cost=250_000)]
        calls = [call(1, inp=1_000_000, out=0)]
        s = sim(make(calls, tasks, stats), {"kind": "structure", "value": "B"})
        self.assertEqual(s["result"]["simulated"]["cost_list_microusd"]["p50"], 1_250_000)
        s = sim(make(calls, tasks, []), {"kind": "structure", "value": "B"})
        self.assertEqual(s["result"]["simulated"]["saving_microusd"]["p50"], 0)
        self.assertTrue(s["result"]["assumptions_applied"][0]["ratio_basis"].startswith("none"))

    def test_assumptions_compose_in_order(self):
        calls = [call(1, inp=100_000, out=0)]
        s = sim(make(calls), {"kind": "context_cap", "value": 10_000},
                {"kind": "model_swap", "from": "big", "value": "small"})
        self.assertEqual(s["result"]["simulated"]["cost_list_microusd"]["p50"], 10_000)  # 10k tok x $1/M
        self.assertEqual(len(s["result"]["assumptions_applied"]), 2)


class ProposalTest(unittest.TestCase):
    def test_to_proposal_hands_assumptions_and_basis_to_advisor_as_simulated(self):
        got = []
        svc = make([call(1)], proposer=lambda *a: got.append(a) or {"id": "p-1"})
        s = sim(svc, {"kind": "context_cap", "value": 4000})
        self.assertEqual(svc.to_proposal(WS, s["id"]), {"simulation_id": s["id"], "proposal_id": "p-1"})
        ws, origin, change, evidence = got[0]
        self.assertEqual((ws, origin, evidence["provenance"]), (WS, "simulation", "SIMULATED"))
        self.assertEqual(change["assumptions"], s["assumptions"])
        self.assertEqual(evidence["basis"], s["basis"])

    def test_without_advisor_503_and_unknown_simulation_404(self):
        svc = make([call(1)])
        s = sim(svc, {"kind": "context_cap", "value": 4000})
        with self.assertRaises(SimulationError) as e:
            svc.to_proposal(WS, s["id"])
        self.assertEqual(e.exception.status, 503)
        svc.proposer = lambda *a: {"id": "x"}
        with self.assertRaises(SimulationError) as e:
            svc.to_proposal(WS, "nope")
        self.assertEqual(e.exception.status, 404)


try:
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
except ImportError:
    FastAPI = None


@unittest.skipIf(FastAPI is None, "fastapi not installed")
class RouteTest(unittest.TestCase):
    def setUp(self):
        from types import SimpleNamespace
        from app.domains.simulation import router as r, wiring
        self.r = r
        self.orig = r.require_member
        r.require_member = lambda ws, uid, *a: None
        app = FastAPI()
        app.include_router(r.router)
        app.dependency_overrides[r.current_user] = lambda: SimpleNamespace(id=USER)
        wiring.set_service(make([call(1)]))
        self.c = TestClient(app)
        self.addCleanup(wiring.set_service, None)
        self.addCleanup(setattr, r, "require_member", self.orig)

    def test_post_empty_assumptions_422_and_valid_201_then_get(self):
        u = f"/v1/workspaces/{WS}/simulations"
        self.assertEqual(self.c.post(u, json={"assumptions": [], "basis": BASIS}).status_code, 422)
        self.assertEqual(self.c.post(u, json={"basis": BASIS}).status_code, 422)
        r = self.c.post(u, json={"assumptions": [{"kind": "context_cap", "value": 100}], "basis": BASIS})
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.json()["provenance"], "SIMULATED")
        self.assertEqual(self.c.get(f"{u}/{r.json()['id']}").json(), r.json())
        self.assertEqual(self.c.get(f"{u}/nope").status_code, 404)


if __name__ == "__main__":
    unittest.main()

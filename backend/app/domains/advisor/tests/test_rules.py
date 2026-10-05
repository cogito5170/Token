import json
import unittest
from datetime import datetime
from pathlib import Path

from app.domains.advisor.rules import Call, Task, registry

FIX = Path(__file__).resolve().parents[5] / "fixtures" / "advisor"
RULES = registry()
# The production price provider returns the whole price table; R4/R5 need the neighbouring tier's price, which a
# single fixture only lists for its own call models. Prices are identical across fixtures, so merge them.
ALL_PRICES = {}
for _p in sorted(FIX.glob("R*.json")):
    ALL_PRICES.update(json.loads(_p.read_text(encoding="utf-8"))["prices"])


def load(rid):
    d = json.loads((FIX / f"{rid}.json").read_text(encoding="utf-8"))
    calls = [Call(c["id"], c["session"], c["task"], c["model"], c["role"], c["input"], c["cache_read"],
                  c["cache_write"], c["output"], c["context"], c["cost_list_nanousd"], c["cost_cli_microusd"],
                  c["prefix_hash"], c["content_hashes"], datetime.fromisoformat(c["at"].replace("Z", "+00:00")))
             for c in d["calls"]]
    tasks = {t["id"]: Task(t["id"], t["kind"], t["model"], t["outcome"], t["first_try_success"]) for t in d["tasks"]}
    d["prices"] = dict(ALL_PRICES)
    return d, calls, tasks


def run(rid, d, calls, tasks, **override):
    mod = RULES[rid]
    return mod.detect(calls, tasks, d["prices"], {**mod.DEFAULTS, **d["params"], **override})


class FixtureTest(unittest.TestCase):
    def test_every_fixture_reproduced_exactly(self):
        for rid in RULES:
            with self.subTest(rule=rid):
                d, calls, tasks = load(rid)
                f = run(rid, d, calls, tasks)
                e = d["expect"]
                self.assertEqual(f is not None, e["fires"])
                self.assertEqual(f.evidence_call_ids, e["evidence_call_ids"])
                self.assertEqual((f.p10, f.p50, f.p90),
                                 (e["savings_p10_microusd"], e["savings_p50_microusd"], e["savings_p90_microusd"]))
                self.assertLessEqual(f.p10, f.p50)
                self.assertLessEqual(f.p50, f.p90)

    def test_defaults_alone_fire_where_fixture_params_equal_defaults(self):
        d, calls, tasks = load("R1")
        self.assertIsNotNone(RULES["R1"].detect(calls, tasks, d["prices"], dict(RULES["R1"].DEFAULTS)))

    def test_r1_threshold(self):
        d, calls, tasks = load("R1")
        self.assertIsNone(run("R1", d, calls, tasks, T=200000))
        self.assertEqual(run("R1", d, calls, tasks, T=100000).evidence_call_ids, [1])

    def test_r2_needs_same_session(self):
        d, calls, tasks = load("R2")
        for c in calls:
            c.session = c.id   # nothing repeats inside one session any more
        self.assertIsNone(run("R2", d, calls, tasks))

    def test_r3_null_prefix_skipped_and_window(self):
        d, calls, tasks = load("R3")
        for c in calls:
            c.prefix_hash = None
        self.assertIsNone(run("R3", d, calls, tasks))
        d, calls, tasks = load("R3")
        self.assertEqual(run("R3", d, calls, tasks, window_s=60).evidence_call_ids, [2])
        self.assertIsNone(run("R3", d, calls, tasks, min_cache_tokens={"claude-sonnet-5-5": 99999}))

    def test_r4_needs_five_tasks_and_a_lower_tier(self):
        d, calls, tasks = load("R4")
        self.assertIsNone(run("R4", d, calls, tasks, min_tasks=7))
        self.assertIsNone(run("R4", d, calls, tasks, tiers={"claude-sonnet-5-5": 2}))
        tasks["t1"].first_try_success = False
        tasks["t2"].first_try_success = False
        self.assertIsNone(run("R4", d, calls, tasks))   # first-try rate below 90 %

    def test_r5_threshold_and_no_upper(self):
        d, calls, tasks = load("R5")
        self.assertIsNone(run("R5", d, calls, tasks, min_fail_rate="9/10"))
        self.assertIsNone(run("R5", d, calls, tasks, tiers={"claude-haiku-4-5-20251001": 1}))
        self.assertIsNone(run("R5", d, calls, tasks, min_tasks=5))

    def test_r6_ratio_and_min_calls(self):
        d, calls, tasks = load("R6")
        self.assertIsNone(run("R6", d, calls, tasks, min_ratio="3/1"))
        self.assertIsNone(run("R6", d, calls[:9], tasks))
        calls[0].cost_cli_microusd = None   # unknown cli is skipped, never 0
        self.assertEqual(len(run("R6", d, calls, tasks).evidence_call_ids), 11)

    def test_r7_only_checkable_kinds(self):
        d, calls, tasks = load("R7")
        tasks["t1"].kind = "docs"
        self.assertIsNone(run("R7", d, calls, tasks))

    def test_proposals_per_rule(self):
        kinds = {}
        for rid in RULES:
            d, calls, tasks = load(rid)
            kinds[rid] = run(rid, d, calls, tasks).proposal["kind"]
        self.assertEqual(kinds, {"R1": "context_cap", "R2": "config_export", "R3": "template", "R4": "router_tier",
                                 "R5": "router_tier", "R6": "config_export", "R7": "template"})


if __name__ == "__main__":
    unittest.main()

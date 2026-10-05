import json
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.domains.usage.service import CallIn, MemoryStore, TaskIn, UsageError, UsageService

LEDGER = Path(__file__).resolve().parents[5] / "fixtures" / "final_task" / "ledger.jsonl"
WS, SRC, JOB = ("00000000-0000-4000-8000-00000000000%d" % i for i in (1, 2, 3))
T0 = datetime(2026, 3, 1, 12, 0, tzinfo=timezone.utc)


def ledger():
    return [json.loads(l) for l in LEDGER.read_text().splitlines() if l.strip()]


def call_from_ledger(row, i):
    u = row["usage"]
    return CallIn(row["model"], "anthropic", "ga_l0", T0 + timedelta(seconds=i), f"ledger-{i}",
                  input_tokens=u["input_tokens"], cache_read_tokens=u["cache_read_input_tokens"],
                  cache_write_5m_tokens=u["cache_creation_input_tokens"], output_tokens=u["output_tokens"],
                  session=row["run_id"], task=row["run_id"], role=row.get("role"))


def make():
    events = []
    svc = UsageService(MemoryStore(), publish=lambda n, p: events.append((n, p)), now=lambda: T0 + timedelta(days=1))
    return svc, events


class CostingTest(unittest.TestCase):
    def test_every_final_task_call_matches_quota_usd_within_one_micro_usd(self):
        svc, _ = make()
        rows = ledger()
        calls = [call_from_ledger(r, i) for i, r in enumerate(rows)]
        res = svc.load_calls(WS, None, SRC, JOB, calls)
        self.assertEqual((res.inserted, res.rejected), (len(rows), []))
        stored = sorted(svc.store.calls_, key=lambda r: int(r.dedupe_key.split("-")[1]))
        for row, c in zip(rows, stored):
            self.assertIsNotNone(c.cost_list_nanousd)
            self.assertLessEqual(abs(c.cost_list_nanousd / 1000 - round(row["quota_usd"] * 1e6)), 1, row["n"])
            self.assertEqual(c.price_version, 1)

    def test_nulls_stay_null(self):
        svc, _ = make()
        c = CallIn("claude-sonnet-5-5", "anthropic", "otel", T0, "k1")  # nothing reported
        svc.load_calls(WS, None, SRC, JOB, [c])
        r = svc.store.calls_[0]
        self.assertIsNone(r.input_tokens)
        self.assertIsNone(r.context_tokens)
        self.assertIsNone(r.cost_list_nanousd)
        out = svc.call_page(WS)["items"][0]
        self.assertIsNone(out["cost_list_microusd"])
        self.assertIsNone(out["input_tokens"])

    def test_unknown_model_is_rejected_by_index_without_content(self):
        svc, ev = make()
        res = svc.load_calls(WS, None, SRC, JOB, [CallIn("mystery-model", "x", "otel", T0, "k", input_tokens=1)])
        self.assertEqual((res.inserted, res.rejected), (0, [{"index": 0, "code": "unknown_model"}]))
        self.assertEqual(ev, [])


class LoadTest(unittest.TestCase):
    def test_reload_is_idempotent_by_dedupe_key(self):
        svc, ev = make()
        calls = [call_from_ledger(r, i) for i, r in enumerate(ledger()[:20])]
        a = svc.load_calls(WS, None, SRC, JOB, calls)
        before = (svc.summary(WS), [vars(t).copy() for t in svc.store.task_.values()])
        b = svc.load_calls(WS, None, SRC, JOB, calls)
        self.assertEqual((a.inserted, a.duplicates, b.inserted, b.duplicates), (20, 0, 0, 20))
        self.assertEqual(before, (svc.summary(WS), [vars(t).copy() for t in svc.store.task_.values()]))
        self.assertEqual(len(svc.store.calls_), 20)
        self.assertEqual([n for n, _ in ev], ["usage.calls.ingested"])  # nothing new on the reload

    def test_totals_session_task_daily(self):
        svc, _ = make()
        cs = [CallIn("claude-haiku-4-5-20251001", "anthropic", "claude_code", T0 + timedelta(minutes=i), f"d{i}",
                     input_tokens=1000, cache_read_tokens=2000, cache_write_5m_tokens=100, output_tokens=50,
                     cost_cli_microusd=10 if i == 0 else None, session="s1", task="t1") for i in range(3)]
        svc.load_calls(WS, None, SRC, JOB, cs)
        t = next(iter(svc.store.task_.values()))
        self.assertEqual((t.calls, t.input_tokens, t.total_tokens, t.max_call_input), (3, 3000, 3 * 3150, 3100))
        self.assertEqual(t.cost_cli_microusd, 10)
        s = next(iter(svc.store.sess.values()))
        self.assertEqual((s.calls, s.client, s.output_tokens), (3, "claude_code", 150))
        d = svc.store.daily(WS, T0.date(), T0.date(), None)
        self.assertEqual((len(d), d[0].calls, d[0].cli_covered_calls, d[0].cost_cli_microusd), (1, 3, 1, 10))

    def test_task_features_from_task_in(self):
        svc, _ = make()
        svc.load_calls(WS, None, SRC, JOB, [CallIn("claude-sonnet-5-5", "anthropic", "ga_l0", T0, "x", input_tokens=1,
                                                   output_tokens=1, task="r1")],
                       tasks={"r1": TaskIn(kind="feature", structure="B", context_mode="selective", outcome="correct",
                                           outcome_source="fixture", model_primary="claude-sonnet-5-5")})
        t = next(iter(svc.store.task_.values()))
        self.assertEqual((t.structure, t.outcome, t.outcome_source), ("B", "correct", "fixture"))


class ChartTest(unittest.TestCase):
    def setUp(self):
        self.svc, self.ev = make()
        rows = ledger()
        self.svc.load_calls(WS, None, SRC, JOB, [call_from_ledger(r, i) for i, r in enumerate(rows)])

    def test_summary_carries_unit_and_provenance_and_coverage(self):
        s = self.svc.summary(WS)
        for name, m in s["tiles"].items():
            self.assertIn("unit", m, name)
            self.assertIn("provenance", m, name)
        self.assertIsNone(s["tiles"]["cost_cli"]["value"])  # no call reported a CLI cost
        self.assertEqual(s["tiles"]["cost_cli"]["coverage_permille"], 0)
        self.assertGreater(s["tiles"]["cost_list"]["value"], 0)
        for ser in s["trend"]["series"]:
            self.assertTrue(ser["unit"] and ser["provenance"])
        cli = next(x for x in s["trend"]["series"] if x["name"] == "cost_cli")
        self.assertTrue(all(p[1] is None for p in cli["points"]))  # unknown stays null, not 0

    def test_token_series(self):
        for bucket in ("hour", "day", "week"):
            ts = self.svc.token_series(WS, bucket=bucket, group_by="model")
            self.assertEqual(ts["bucket"], bucket)
            self.assertEqual({s["name"].split(":")[1] for s in ts["series"]},
                             {"input", "cache_read", "cache_write", "output"})
            for s in ts["series"]:
                self.assertEqual((s["unit"], s["provenance"]), ("tokens", "MEASURED"))
        day = self.svc.token_series(WS)
        total = sum(p[1] for s in day["series"] for p in s["points"])
        self.assertEqual(total, sum(r.input_tokens + r.cache_read_tokens + r.cache_write_5m_tokens + r.output_tokens
                                    for r in self.svc.store.calls_))
        with self.assertRaises(UsageError):
            self.svc.token_series(WS, bucket="year")

    def test_call_size_histogram_and_outliers(self):
        h = self.svc.call_size(WS, threshold=100_000)
        self.assertEqual((h["unit"], h["provenance"]), ("tokens", "CALCULATED"))
        self.assertEqual(sum(b["count"] for b in h["bins"]), len(self.svc.store.calls_))
        for b in h["bins"]:
            self.assertEqual(b["hi"], b["lo"] * 2 if b["lo"] else 1)
        self.assertTrue(h["outliers"])
        self.assertTrue(all(o["context_tokens"] >= 100_000 for o in h["outliers"]))
        self.assertEqual(self.svc.call_size(WS, threshold=10**9)["outliers"], [])

    def test_pages_walk_without_gaps(self):
        seen, cur = [], None
        while True:
            p = self.svc.call_page(WS, cursor=cur, limit=50)
            seen += [c["id"] for c in p["items"]]
            cur = p["next_cursor"]
            if not cur:
                break
        self.assertEqual(sorted(seen), sorted(set(seen)))
        self.assertEqual(len(seen), len(self.svc.store.calls_))
        self.assertEqual(len(self.svc.call_page(WS, min_input=100_000)["items"]),
                         sum(1 for r in self.svc.store.calls_ if r.context_tokens >= 100_000))
        self.assertEqual(len(self.svc.session_page(WS, limit=5)["items"]), 5)
        self.assertTrue(self.svc.task_page(WS, limit=5)["next_cursor"])


class CompareTest(unittest.TestCase):
    def _tasks(self, svc, specs):
        for i, (structure, outcome, tokens) in enumerate(specs):
            svc.load_calls(WS, None, SRC, JOB, [CallIn("claude-haiku-4-5-20251001", "anthropic", "ga_l0",
                                                       T0 + timedelta(minutes=i), f"c{i}", input_tokens=tokens,
                                                       output_tokens=0, task=f"r{i}")],
                           tasks={f"r{i}": TaskIn(structure=structure, outcome=outcome)})

    def test_groups_ranges_and_accuracy(self):
        svc, _ = make()
        self._tasks(svc, [("A", "correct", 100), ("A", "correct", 300), ("A", "incorrect", 200), ("A", "correct", 200),
                          ("B", "correct", 50), ("C", "incorrect", 70)])
        out = svc.compare(WS, ["structure"])
        keys = [g["key"]["structure"] for g in out["groups"]]
        self.assertEqual(keys, ["A", "B"])  # C has no correct task: left out
        a = out["groups"][0]
        self.assertEqual((a["tasks"], a["correct"], a["accuracy"]["value"]), (4, 3, 750))
        r = a["tokens_per_correct"]  # values / 0.75 = 133, 267, 400, 267 -> sorted 133 267 267 400, P10 = 173
        self.assertEqual((r["p10"], r["p50"], r["p90"], r["unit"], r["provenance"]), (173, 267, 360, "tokens",
                                                                                      "CALCULATED"))
        self.assertLessEqual(r["p10"], r["p50"])
        self.assertLessEqual(r["p50"], r["p90"])
        with self.assertRaises(UsageError):
            svc.compare(WS, ["nope"])


class TaskPatchTest(unittest.TestCase):
    def test_patch_sets_user_outcome_and_emits_once(self):
        svc, ev = make()
        svc.load_calls(WS, None, SRC, JOB, [CallIn("claude-sonnet-5-5", "anthropic", "claude_code", T0, "p",
                                                   input_tokens=5, output_tokens=5, task="r")])
        tid = next(iter(svc.store.task_))
        t = svc.update_task(WS, "u1", tid, outcome="correct", kind="bug")
        self.assertEqual((t["outcome"], t["kind"]), ("correct", "bug"))
        self.assertEqual(svc.store.task_[tid].outcome_source, "user")
        svc.update_task(WS, "u1", tid, outcome="correct")  # unchanged: no second event
        ev = [e for e in ev if e[0] == "usage.task.outcome_set"]
        self.assertEqual(len(ev), 1)
        self.assertEqual(ev[0][1]["task_id"], tid)
        for bad in ({"outcome": "maybe"}, {"kind": "x"}):
            with self.assertRaises(UsageError) as c:
                svc.update_task(WS, "u1", tid, **bad)
            self.assertEqual(c.exception.status, 422)
        with self.assertRaises(UsageError) as c:
            svc.update_task(WS, "u1", "00000000-0000-4000-8000-0000000000ff", outcome="correct")
        self.assertEqual(c.exception.status, 404)

    def test_other_workspace_task_is_not_found(self):
        svc, _ = make()
        svc.load_calls(WS, None, SRC, JOB, [CallIn("claude-sonnet-5-5", "anthropic", "claude_code", T0, "p", task="r")])
        with self.assertRaises(UsageError):
            svc.update_task("00000000-0000-4000-8000-0000000000aa", "u", next(iter(svc.store.task_)), outcome="correct")


class ModelsTest(unittest.TestCase):
    def test_seed_prices_follow_final_task_table(self):
        by = {m["id"]: m["price"] for m in make()[0].list_models()}
        h, s = by["claude-haiku-4-5-20251001"], by["claude-sonnet-5-5"]
        self.assertEqual((h["input_per_mtok_microusd"], h["output_per_mtok_microusd"]), (1_000_000, 5_000_000))
        self.assertEqual((s["input_per_mtok_microusd"], s["output_per_mtok_microusd"]), (2_000_000, 10_000_000))
        self.assertEqual((h["cache_write_5m_per_mtok_microusd"], h["cache_read_per_mtok_microusd"]),
                         (1_250_000, 100_000))
        self.assertEqual(h["cache_write_1h_per_mtok_microusd"], 2_000_000)


if __name__ == "__main__":
    unittest.main()

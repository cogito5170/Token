"""CMD-GC24 S3: usage.api exposes hashes / nano cost on calls, first_try_success / user_id on tasks, and prices()."""
import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone

from app.domains.usage import api as usage_api
from app.domains.usage import wiring as usage_wiring
from app.domains.usage.service import CallIn, MemoryStore, TaskIn, UsageService

WS, SRC, JOB = ("00000000-0000-4000-8000-00000000000%d" % i for i in (1, 2, 3))
USER = "00000000-0000-4000-8000-0000000000d1"
NOW = datetime(2026, 3, 10, tzinfo=timezone.utc)
HAIKU = "claude-haiku-4-5-20251001"
HASHES = ["aaaaaaaaaaaa:150", "bbbbbbbbbbbb:50"]


def call(i, **kw):
    return CallIn(HAIKU, "anthropic", "claude_code", datetime(2026, 3, 1, 10, i, tzinfo=timezone.utc), f"k{i}",
                  input_tokens=5000, output_tokens=200, **kw)


class UsageExtrasTests(unittest.TestCase):
    def setUp(self):
        self.svc = UsageService(MemoryStore(), now=lambda: NOW)
        usage_wiring.set_service(self.svc)
        self.addCleanup(usage_wiring.set_service, None)

    def page(self):
        return sorted(usage_api.calls(WS, NOW - timedelta(days=30), NOW)["items"], key=lambda r: r["id"])

    def test_calls_expose_hashes_and_nano_cost(self):
        usage_api.load_calls(WS, None, SRC, JOB, [call(0, prompt_prefix_hash="f" * 64, content_hashes=HASHES)])
        item = self.page()[0]
        self.assertEqual((item["prompt_prefix_hash"], item["content_hashes"]), ("f" * 64, HASHES))
        self.assertEqual(item["cost_list_nanousd"], 5000 * 1000 + 200 * 5000)  # haiku $1 / $5 per Mtok
        self.assertEqual(item["cost_list_microusd"], 6000)

    def test_null_hashes_stay_null(self):
        usage_api.load_calls(WS, None, SRC, JOB, [call(0)])
        item = self.page()[0]
        self.assertIsNone(item["prompt_prefix_hash"])
        self.assertIsNone(item["content_hashes"])

    def test_tasks_expose_first_try_success_and_user(self):
        a, b = call(0, session="t1", task="t1"), call(1, session="t2", task="t2")
        usage_api.load_calls(WS, None, SRC, JOB, [a, b], tasks={"t1": TaskIn(first_try_success=True, user_id=USER),
                                                                "t2": TaskIn(first_try_success=False)})
        c = call(2, session="t3", task="t3")
        usage_api.load_calls(WS, None, SRC, JOB, [c], tasks={"t3": TaskIn()})
        by = {t["external_ref"]: t for t in usage_api.tasks(WS, NOW - timedelta(days=30), NOW)["items"]}
        self.assertEqual((by["t1"]["first_try_success"], by["t1"]["user_id"]), (True, USER))
        self.assertEqual((by["t2"]["first_try_success"], by["t2"]["user_id"]), (False, None))
        self.assertEqual((by["t3"]["first_try_success"], by["t3"]["user_id"]), (None, None))  # unknown, not False

    def test_prices_final_task_with_version(self):
        p = usage_api.prices()
        self.assertEqual(p[HAIKU], {"in": 1_000_000, "out": 5_000_000, "cr": 100_000, "cw5": 1_250_000,
                                    "cw1": 2_000_000, "version": 1})
        self.assertEqual((p["claude-sonnet-5-5"]["in"], p["claude-sonnet-5-5"]["out"]), (2_000_000, 10_000_000))

    def test_prices_use_newest_version(self):
        store = self.svc.store
        store._prices.append(replace(store._prices[0], version=2, input=1_500_000))
        got = usage_api.prices()[store._prices[0].model_id]
        self.assertEqual((got["version"], got["in"]), (2, 1_500_000))


if __name__ == "__main__":
    unittest.main()

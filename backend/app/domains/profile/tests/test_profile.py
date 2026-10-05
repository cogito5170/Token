import unittest
from types import SimpleNamespace
from unittest import mock

try:
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
except ImportError:
    FastAPI = None

from app.domains.profile.service import MemoryStore, ProfileError, ProfileService, compute_stats, recommend

WS = "00000000-0000-4000-8000-000000000001"


def task(kind, model, outcome, tokens, cost, cli=None, structure="single", ctx="selective", **kw):
    return {"kind": kind, "model_primary": model, "outcome": outcome, "total_tokens": tokens,
            "cost_list_microusd": cost, "cost_cli_microusd": cli, "structure": structure, "context_mode": ctx, **kw}


# fixture: feature/opus: 6 tasks, 4 correct, 600k tokens, 3_000_000 micro -> per correct 150k tokens, 750_000 micro
#          feature/haiku: 6 tasks, 5 correct, 300k tokens, 600_000 micro -> per correct 60k tokens, 120_000 micro
def fixture(user=None):
    extra = {} if user is None else {"user_id": user}
    ts = [task("feature", "claude-opus-5-5", "correct" if i < 4 else "incorrect", 100_000, 500_000, 900_000, **extra)
          for i in range(6)]
    ts += [task("feature", "claude-haiku-4-5", "correct" if i < 5 else "incorrect", 50_000, 100_000, 150_000, **extra)
           for i in range(6)]
    return ts


def svc(tasks, proposer=None):
    s = ProfileService(MemoryStore(), lambda ws: tasks, proposer)
    return s


class StatsTest(unittest.TestCase):
    def test_per_correct_matches_hand_computation(self):
        by = {s.model_id: s for s in compute_stats(fixture())}
        o, h = by["claude-opus-5-5"], by["claude-haiku-4-5"]
        self.assertEqual((o.tasks, o.correct), (6, 4))
        self.assertEqual(o.tokens_per_correct, 150_000)          # 600_000 / 4
        self.assertEqual(o.cost_list_per_correct_nanousd, 750_000_000)  # 3_000_000 micro / 4 * 1000
        self.assertEqual(o.cost_cli_per_correct_microusd, 1_350_000)    # 5_400_000 / 4
        self.assertEqual(h.tokens_per_correct, 60_000)           # 300_000 / 5
        self.assertEqual(h.cost_list_per_correct_nanousd, 120_000_000)  # 600_000 / 5 * 1000

    def test_no_correct_means_no_per_correct(self):
        s = compute_stats([task("bug", "m", "incorrect", 10, 10)])[0]
        self.assertIsNone(s.tokens_per_correct)
        self.assertIsNone(s.cost_list_per_correct_nanousd)

    def test_json_shape(self):
        s = svc(fixture())
        s.put_profile(WS, "u1", {})
        s.refresh_stats(WS)
        row = [r for r in s.stats(WS, "u1") if r["model_id"] == "claude-opus-5-5"][0]
        self.assertEqual(row["cost_list_per_correct"]["value"], 750_000)
        self.assertEqual(row["tokens_per_correct"]["value"], 150_000)

    def test_other_users_stats_never_returned(self):
        s = svc(fixture("u1") + [task("bug", "claude-opus-5-5", "correct", 1, 1, user_id="u2")])
        s.put_profile(WS, "u1", {})
        s.put_profile(WS, "u2", {})
        s.refresh_stats(WS)
        self.assertEqual({r["task_kind"] for r in s.stats(WS, "u1")}, {"feature"})
        self.assertEqual({r["task_kind"] for r in s.stats(WS, "u2")}, {"bug"})
        self.assertEqual(s.stats(WS, "u3"), [])
        self.assertEqual(s.stats("00000000-0000-4000-8000-0000000000ee", "u1"), [])

    def test_refresh_on_usage_event(self):
        s = svc(fixture())
        s.put_profile(WS, "u1", {})
        self.assertEqual(s.stats(WS, "u1"), [])
        s.on_usage_ingested("usage.calls.ingested", {"workspace_id": WS})
        self.assertEqual(len(s.stats(WS, "u1")), 2)
        v1 = s.store.stats(WS, "u1")[0].version
        s.on_usage_ingested("usage.calls.ingested", {"workspace_id": WS})
        self.assertEqual(s.store.stats(WS, "u1")[0].version, v1 + 1)


class RecommendTest(unittest.TestCase):
    def rec(self, tasks, floor=None):
        s = svc(tasks)
        s.put_profile(WS, "u1", {"quality_floor_permille": floor})
        s.refresh_stats(WS)
        return s.recommendations(WS, "u1")

    def test_recommends_cheaper_config(self):
        # current = opus (first max by tasks tie-break -> opus sorts after haiku), saving (750k-120k)/750k = 84.0 %
        r = self.rec(fixture(), floor=800)
        self.assertEqual(len(r), 1)
        self.assertEqual(r[0]["saving"]["value"], 840)
        self.assertEqual(r[0]["evidence_n"], 6)
        self.assertEqual(r[0]["recommended_config"]["model"], "claude-haiku-4-5")
        self.assertIn("84.0%", r[0]["headline"])
        self.assertIn("근거 6 건", r[0]["headline"])

    def test_quality_floor_blocks(self):
        # haiku correct rate = 5/6 = 833 permille
        self.assertEqual(len(self.rec(fixture(), floor=833)), 1)
        self.assertEqual(self.rec(fixture(), floor=834), [])

    def test_default_floor_applies_when_unset(self):
        weak = [task("feature", "claude-opus-5-5", "correct", 100, 500, structure="A") for _ in range(6)]
        weak += [task("feature", "claude-haiku-4-5", "correct" if i < 3 else "incorrect", 10, 10) for i in range(6)]
        self.assertEqual(self.rec(weak, floor=None), [])        # 500 permille < default 800

    def test_evidence_below_five_never_recommended(self):
        ts = [task("feature", "claude-opus-5-5", "correct", 100_000, 500_000) for _ in range(6)]
        ts += [task("feature", "claude-haiku-4-5", "correct", 1, 1) for _ in range(4)]   # 4 tasks, perfect and cheap
        self.assertEqual(self.rec(ts, floor=0), [])
        ts.append(task("feature", "claude-haiku-4-5", "correct", 1, 1))                   # now 5
        self.assertEqual(len(self.rec(ts, floor=0)), 1)

    def test_not_cheaper_not_recommended(self):
        ts = [task("feature", "a", "correct", 1, 100) for _ in range(6)]
        ts += [task("feature", "b", "correct", 1, 100) for _ in range(5)]
        self.assertEqual(self.rec(ts, floor=0), [])

    def test_recommend_pure(self):
        self.assertEqual(recommend([], 0), [])


class ProfileTest(unittest.TestCase):
    def test_defaults_store_bodies_false(self):
        s = svc([])
        self.assertIs(s.get_profile(WS, "u1")["store_bodies"], False)
        self.assertIs(s.put_profile(WS, "u1", {"team_size": 3})["store_bodies"], False)

    def test_crud_and_isolation(self):
        s = svc([])
        s.put_profile(WS, "u1", {"quality_floor_permille": 900, "preferred_models": ["m"], "billing_mode": "api",
                                 "store_bodies": True})
        got = s.get_profile(WS, "u1")
        self.assertEqual((got["quality_floor_permille"], got["preferred_models"], got["store_bodies"]), (900, ["m"], True))
        self.assertIs(s.get_profile(WS, "u2")["store_bodies"], False)
        self.assertIsNone(s.get_profile(WS, "u2")["quality_floor_permille"])

    def test_validation(self):
        s = svc([])
        for bad in ({"quality_floor_permille": 1001}, {"quality_floor_permille": -1}, {"billing_mode": "x"},
                    {"store_bodies": "yes"}, {"team_size": 1.5}, {"nope": 1}, {"preferred_models": "m"}):
            with self.assertRaises(ProfileError, msg=str(bad)) as cm:
                s.put_profile(WS, "u1", bad)
            self.assertEqual(cm.exception.status, 422)


class HandoffTest(unittest.TestCase):
    def setUp(self):
        self.calls = []

        def proposer(ws, origin, change, evidence):
            self.calls.append((ws, origin, change, evidence))
            return {"id": "00000000-0000-4000-8000-0000000000aa"}
        self.s = svc(fixture(), proposer)
        self.s.put_profile(WS, "u1", {"quality_floor_permille": 800})
        self.s.refresh_stats(WS)
        self.rid = self.s.recommendations(WS, "u1")[0]["id"]

    def test_hand_off_to_advisor(self):
        out = self.s.to_proposal(WS, "u1", self.rid)
        self.assertEqual(out["proposal_id"], "00000000-0000-4000-8000-0000000000aa")
        ws, origin, change, ev = self.calls[0]
        self.assertEqual((ws, origin, change["to"]["model"], ev["evidence_n"]), (WS, "profile", "claude-haiku-4-5", 6))
        self.assertEqual(self.s.recommendations(WS, "u1")[0]["proposal_id"], out["proposal_id"])
        self.assertEqual(self.s.recommendations(WS, "u1")[0]["id"], self.rid)   # stable id across recompute

    def test_other_user_cannot_hand_off(self):
        with self.assertRaises(ProfileError) as cm:
            self.s.to_proposal(WS, "u2", self.rid)
        self.assertEqual(cm.exception.status, 404)
        self.assertEqual(self.calls, [])

    def test_no_advisor_is_503(self):
        self.s.proposer = None
        with self.assertRaises(ProfileError) as cm:
            self.s.to_proposal(WS, "u1", self.rid)
        self.assertEqual(cm.exception.status, 503)


@unittest.skipIf(FastAPI is None, "fastapi not installed")
class RouteTest(unittest.TestCase):
    def setUp(self):
        from app.domains.profile import router as r, wiring
        self.s = svc(fixture())
        wiring.set_service(self.s)
        self.addCleanup(wiring.set_service, None)
        self.uid = {"id": "u1"}

        def fake_require(ws, uid, min_role="viewer"):
            if ws != WS:
                raise __import__("fastapi").HTTPException(404, detail={"code": "not_found", "message": "x"})
        p = mock.patch.object(r, "require_member", fake_require)
        p.start()
        self.addCleanup(p.stop)
        app = FastAPI()
        app.include_router(r.router)
        app.dependency_overrides[r.current_user] = lambda: SimpleNamespace(id=self.uid["id"])
        self.c = TestClient(app)

    def test_routes(self):
        base = f"/v1/workspaces/{WS}/profile"
        self.assertIs(self.c.get(base).json()["store_bodies"], False)
        self.assertEqual(self.c.put(base, json={"quality_floor_permille": 800}).status_code, 200)
        self.assertEqual(self.c.put(base, json={"quality_floor_permille": 5000}).status_code, 422)
        self.s.refresh_stats(WS)
        self.assertEqual(len(self.c.get(base + "/stats").json()), 2)
        self.assertEqual(len(self.c.get(base + "/recommendations").json()), 1)
        self.uid["id"] = "u2"
        self.assertEqual(self.c.get(base + "/stats").json(), [])
        self.assertEqual(self.c.get("/v1/workspaces/00000000-0000-4000-8000-0000000000ee/profile").status_code, 404)


if __name__ == "__main__":
    unittest.main()

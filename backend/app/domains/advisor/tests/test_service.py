import json
import unittest
from datetime import datetime, timedelta, timezone

from app.domains.advisor.service import AdvisorError, AdvisorService, MemoryStore

from .test_rules import ALL_PRICES, FIX

WS = "00000000-0000-4000-8000-000000000001"
DEV = "00000000-0000-4000-8000-0000000000d1"
ADM = "00000000-0000-4000-8000-0000000000a1"
NOW = datetime(2026, 10, 10, 12, 0, tzinfo=timezone.utc)


def usage_from(rid):
    """usage.api.calls / tasks stand-ins serving one fixture in the HTTP shape (two pages to exercise paging)."""
    d = json.loads((FIX / f"{rid}.json").read_text(encoding="utf-8"))
    calls = [{"id": c["id"], "occurred_at": c["at"], "model_id": c["model"], "role": c["role"], "session_id": c["session"],
              "task_id": c["task"], "input_tokens": c["input"], "cache_read_tokens": c["cache_read"],
              "cache_write_tokens": c["cache_write"], "output_tokens": c["output"], "context_tokens": c["context"],
              "cost_list_nanousd": c["cost_list_nanousd"], "cost_cli_microusd": c["cost_cli_microusd"],
              "prompt_prefix_hash": c["prefix_hash"], "content_hashes": c["content_hashes"]} for c in d["calls"]]
    tasks = [{"id": t["id"], "kind": t["kind"], "model_primary": t["model"], "outcome": t["outcome"],
              "first_try_success": t["first_try_success"]} for t in d["tasks"]]

    def pager(items):
        def fn(ws, frm, to, cursor=None, limit=100):
            off = int(cursor or 0)
            return {"items": items[off:off + 2], "next_cursor": str(off + 2) if off + 2 < len(items) else None}
        return fn
    return pager(calls), pager(tasks), d["params"]


class Fakes:
    def __init__(self):
        self.audit, self.events, self.allowed, self.checks = [], [], True, []

    def record(self, action, actor, detail=None, **kw):
        self.audit.append((action, actor, detail))

    def check(self, ws, scope, extra, project_id=None, cost_cli=None):
        self.checks.append((ws, scope, extra))
        return {"allowed": self.allowed, "blocked_by": [] if self.allowed else
                [{"budget_id": "b1", "measure": "list", "limit_microusd": 1, "used_microusd": 1, "after_microusd": 2,
                  "action_at_limit": "stop"}]}

    def actions(self):
        return [a for a, _, _ in self.audit]


def make(rid="R1"):
    f = Fakes()
    calls, tasks, params = usage_from(rid)
    store = MemoryStore()
    store.rules[(WS, rid)] = (True, params)
    svc = AdvisorService(store, calls, tasks, lambda: ALL_PRICES, f.check, f.record,
                         publish=lambda n, p: f.events.append(n), now=lambda: NOW)
    return svc, f, store


def proposal(svc, kind="context_cap", change=None):
    return svc.submit_proposal(WS, "simulation", "sim-1", kind, change or {"context_cap_tokens": 20000}, 500, actor=DEV)


class RunRulesTest(unittest.TestCase):
    def test_run_creates_finding_and_proposal_with_fixture_numbers(self):
        svc, f, _ = make("R1")
        rows = svc.run_rules(WS)
        self.assertEqual([r.rule_id for r in rows], ["R1"])
        v = svc.list_findings(WS)[0]
        self.assertEqual((v["savings"]["p10"], v["savings"]["p50"], v["savings"]["p90"]), (102548, 205097, 255947))
        self.assertEqual(v["evidence_call_ids"], [1, 3])
        self.assertEqual(v["savings"]["provenance"], "ESTIMATED")
        p = svc.get_proposal(WS, v["proposal_id"])
        self.assertEqual((p.state, p.kind, p.expected_savings_microusd), ("proposed", "context_cap", 205097))
        self.assertIn("proposal.create", f.actions())
        self.assertEqual(f.events[:1], ["advisor.finding.created"])

    def test_rerun_updates_instead_of_duplicating(self):
        svc, _, store = make("R1")
        svc.run_rules(WS, NOW - timedelta(days=30), NOW)
        svc.run_rules(WS, NOW - timedelta(days=30), NOW)
        self.assertEqual((len(store.findings), len(store.proposals)), (1, 1))

    def test_disabled_rule_does_not_run(self):
        svc, _, store = make("R1")
        store.rules[(WS, "R1")] = (False, {})
        self.assertEqual(svc.run_rules(WS), [])

    def test_rule_params_overlay_defaults(self):
        svc, _, _ = make("R1")
        r1 = [r for r in svc.list_rules(WS) if r["rule_id"] == "R1"][0]
        self.assertEqual(r1["params"], {"T": 50000, "C": 20000})
        self.assertEqual(len(svc.list_rules(WS)), 7)


class GateTest(unittest.TestCase):
    def test_apply_without_confirm_is_refused(self):
        svc, f, _ = make()
        p = proposal(svc)
        svc.decide(WS, DEV, "developer", p.id, "accept")
        with self.assertRaises(AdvisorError) as e:
            svc.decide(WS, DEV, "developer", p.id, "apply", confirm=False)
        self.assertEqual(e.exception.code, "confirm_required")
        self.assertEqual(svc.get_proposal(WS, p.id).state, "accepted")
        self.assertIn("proposal.blocked", f.actions())
        for c in (None, "true", 1):   # only the boolean True counts
            with self.assertRaises(AdvisorError):
                svc.decide(WS, DEV, "developer", p.id, "apply", confirm=c)
        self.assertNotIn("proposal.apply", f.actions())

    def test_apply_with_confirm_applies_and_audits(self):
        svc, f, _ = make()
        p = proposal(svc)
        svc.decide(WS, DEV, "developer", p.id, "accept")
        out = svc.decide(WS, DEV, "developer", p.id, "apply", confirm=True)
        self.assertEqual(out.state, "applied")
        self.assertEqual(f.actions(), ["proposal.create", "proposal.accept", "proposal.apply"])
        self.assertEqual([d.decision for d in svc.decisions(p.id)], ["accept", "apply"])
        self.assertEqual(f.checks, [(WS, "workspace", 0)])
        self.assertIn("advisor.proposal.applied", f.events)

    def test_over_budget_apply_is_blocked(self):
        svc, f, _ = make()
        f.allowed = False
        p = proposal(svc, change={"context_cap_tokens": 1, "extra_cost_microusd": 10**9})
        svc.decide(WS, DEV, "developer", p.id, "accept")
        out = svc.decide(WS, DEV, "developer", p.id, "apply", confirm=True)
        self.assertEqual(out.state, "blocked")
        self.assertIn("b1", out.blocked_reason)
        self.assertEqual(f.checks[0][2], 10**9)
        self.assertEqual(f.actions()[-1], "proposal.blocked")
        d = svc.decisions(p.id)[-1]
        self.assertEqual((d.policy_ok, d.budget_ok), (True, False))
        self.assertNotIn("proposal.apply", f.actions())

    def test_policy_blocks_before_budget_is_asked(self):
        svc, f, _ = make()
        p = proposal(svc, kind="repo_change", change={"path": "x"})
        svc.decide(WS, ADM, "admin", p.id, "accept")
        out = svc.decide(WS, DEV, "developer", p.id, "apply", confirm=True)
        self.assertEqual(out.state, "blocked")
        self.assertTrue(out.blocked_reason.startswith("policy"))
        self.assertEqual(f.checks, [])
        self.assertFalse(svc.decisions(p.id)[-1].policy_ok)

    def test_viewer_cannot_decide(self):
        svc, f, _ = make()
        p = proposal(svc)
        with self.assertRaises(AdvisorError) as e:
            svc.decide(WS, DEV, "viewer", p.id, "accept")
        self.assertEqual(e.exception.status, 403)
        self.assertEqual(svc.get_proposal(WS, p.id).state, "proposed")
        self.assertIn("proposal.blocked", f.actions())

    def test_apply_needs_accept_first(self):
        svc, _, _ = make()
        p = proposal(svc)
        with self.assertRaises(AdvisorError) as e:
            svc.decide(WS, DEV, "developer", p.id, "apply", confirm=True)
        self.assertEqual(e.exception.status, 409)

    def test_reject_is_final_and_audited(self):
        svc, f, _ = make()
        p = proposal(svc)
        svc.decide(WS, DEV, "developer", p.id, "reject", note="no")
        self.assertEqual(f.actions()[-1], "proposal.reject")
        for dec in ("accept", "apply"):
            with self.assertRaises(AdvisorError):
                svc.decide(WS, DEV, "developer", p.id, dec, confirm=True)

    def test_expired_proposal_cannot_be_applied(self):
        svc, _, store = make()
        p = proposal(svc)
        svc.decide(WS, DEV, "developer", p.id, "accept")
        svc.now = lambda: NOW + timedelta(days=31)
        with self.assertRaises(AdvisorError):
            svc.decide(WS, DEV, "developer", p.id, "apply", confirm=True)
        self.assertEqual(svc.get_proposal(WS, p.id).state, "expired")

    def test_other_workspace_cannot_see_proposal(self):
        svc, _, _ = make()
        p = proposal(svc)
        with self.assertRaises(AdvisorError) as e:
            svc.decide("00000000-0000-4000-8000-0000000000ff", DEV, "admin", p.id, "accept")
        self.assertEqual(e.exception.status, 404)

    def test_invalid_submissions(self):
        svc, _, _ = make()
        for args in (("nobody", "r", "template", {}), ("advisor", "r", "nope", {}), ("advisor", "", "template", {})):
            with self.assertRaises(AdvisorError):
                svc.submit_proposal(WS, *args)

    def test_audit_detail_has_ids_and_numbers_only(self):
        svc, f, _ = make()
        p = proposal(svc)
        svc.decide(WS, DEV, "developer", p.id, "accept", note="free text note")
        for _, _, detail in f.audit:
            self.assertNotIn("note", detail)
            self.assertNotIn("change", detail)


if __name__ == "__main__":
    unittest.main()

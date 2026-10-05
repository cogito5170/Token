"""Advisor use cases: run rules R1-R7 over a period, findings, Proposals and the apply gate.

AI is not the decision maker: every output is a Proposal (state machine proposed -> accepted | rejected -> applied |
blocked | expired). `apply` runs only after policy -> quota.check -> user confirm, and every step is written to
proposal_decisions (domain state) and to the audit log. MVP "apply" is an export / in-platform setting only; this
service never touches a user's repository or an external system.

Everything outside is injected (usage readers, prices, quota.check, audit.record, publish) so rules test without a DB.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta, timezone
from typing import Callable

from .rules import DETECTOR_VERSION, RULE_IDS, Call, Finding, Task, registry

ORIGINS = ("advisor", "simulation", "profile", "run_node")
KINDS = ("config_export", "budget_change", "router_tier", "context_cap", "template", "repo_change")
STATES = ("proposed", "accepted", "rejected", "applied", "expired", "blocked")
ADMIN_KINDS = ("repo_change", "budget_change")
RANK = {"viewer": 0, "developer": 1, "admin": 2}
DEFAULT_PERIOD_DAYS = 30
PROPOSAL_TTL_DAYS = 30
NAMES = {"R1": "bulk_injection", "R2": "reread", "R3": "cache_miss", "R4": "model_overkill", "R5": "model_underkill",
         "R6": "runner_overhead", "R7": "judge_waste"}


class AdvisorError(Exception):
    """code: not_found | invalid_request | conflict | forbidden | confirm_required"""

    def __init__(self, code: str, message: str, status: int):
        super().__init__(message)
        self.code, self.message, self.status = code, message, status


@dataclass
class FindingRow:
    id: str
    workspace_id: str
    rule_id: str
    period_start: datetime
    period_end: datetime
    finding: Finding
    created_at: datetime


@dataclass
class ProposalRow:
    id: str
    workspace_id: str
    origin: str
    origin_ref: str
    kind: str
    change: dict
    expected_savings_microusd: int | None
    state: str
    blocked_reason: str | None
    created_at: datetime
    expires_at: datetime | None


@dataclass
class DecisionRow:
    proposal_id: str
    decided_by: str
    decision: str
    policy_ok: bool
    budget_ok: bool
    note: str
    decided_at: datetime


class MemoryStore:
    def __init__(self) -> None:
        self.rules: dict[tuple, tuple] = {}
        self.findings: dict[str, FindingRow] = {}
        self.proposals: dict[str, ProposalRow] = {}
        self.decisions: list[DecisionRow] = []

    def rule_settings(self, ws: str) -> dict[str, tuple[bool, dict]]:
        return {r: v for (w, r), v in self.rules.items() if w == ws}

    def upsert_finding(self, ws, f: Finding, start, end, now) -> FindingRow:
        for row in self.findings.values():
            if (row.workspace_id, row.rule_id, row.period_start, row.period_end) == (ws, f.rule_id, start, end):
                row.finding = f
                return row
        row = FindingRow(str(uuid.uuid4()), ws, f.rule_id, start, end, f, now)
        self.findings[row.id] = row
        return row

    def list_findings(self, ws, frm, to) -> list[FindingRow]:
        return sorted((r for r in self.findings.values() if r.workspace_id == ws and r.period_end >= frm
                       and r.period_start <= to), key=lambda r: (r.created_at, r.rule_id))

    def add_proposal(self, p: ProposalRow) -> ProposalRow:
        self.proposals[p.id] = p
        return p

    def get_proposal(self, ws, pid) -> ProposalRow | None:
        p = self.proposals.get(pid)
        return p if p and p.workspace_id == ws else None

    def list_proposals(self, ws, state=None) -> list[ProposalRow]:
        return sorted((p for p in self.proposals.values() if p.workspace_id == ws and (state is None or p.state == state)),
                      key=lambda p: p.created_at, reverse=True)

    def by_origin(self, ws, origin, ref) -> ProposalRow | None:
        return next((p for p in self.proposals.values() if (p.workspace_id, p.origin, p.origin_ref) == (ws, origin, ref)),
                    None)

    def update_proposal(self, p: ProposalRow) -> ProposalRow:
        self.proposals[p.id] = p
        return p

    def add_decision(self, d: DecisionRow) -> None:
        self.decisions.append(d)

    def decisions_of(self, pid) -> list[DecisionRow]:
        return [d for d in self.decisions if d.proposal_id == pid]


def _utc(s):
    return s if isinstance(s, datetime) else datetime.fromisoformat(str(s).replace("Z", "+00:00"))


def normalize_call(r: dict) -> Call:
    """usage.api.calls item (HTTP shape) -> Call. Keys usage does not expose yet stay empty/None (never 0)."""
    nano = r.get("cost_list_nanousd")
    if nano is None and r.get("cost_list_microusd") is not None:
        nano = r["cost_list_microusd"] * 1000
    return Call(int(r["id"]), r.get("session_id"), r.get("task_id"), r["model_id"], r.get("role"),
                r.get("input_tokens") or 0, r.get("cache_read_tokens") or 0, r.get("cache_write_tokens") or 0,
                r.get("output_tokens") or 0, r.get("context_tokens") or 0, nano, r.get("cost_cli_microusd"),
                r.get("prompt_prefix_hash"), list(r.get("content_hashes") or []),
                _utc(r["occurred_at"]) if r.get("occurred_at") else None)


def normalize_task(r: dict) -> Task:
    return Task(str(r["id"]), r.get("kind"), r.get("model_primary"), r.get("outcome"), r.get("first_try_success"))


class AdvisorService:
    def __init__(self, store, calls: Callable, tasks: Callable, prices: Callable[[], dict], quota_check: Callable,
                 audit: Callable, publish: Callable[[str, dict], object] = lambda n, p: 0,
                 now: Callable[[], datetime] = lambda: datetime.now(timezone.utc)) -> None:
        """calls(ws, t_from, t_to, cursor=None, limit=100) / tasks(...) are usage.api.calls / tasks (paged dicts)."""
        self.store, self._calls, self._tasks, self._prices = store, calls, tasks, prices
        self.quota_check, self.audit, self.publish, self.now = quota_check, audit, publish, now
        self.rules = registry()

    # -- rules ---------------------------------------------------------------------------------------------
    def list_rules(self, ws: str) -> list[dict]:
        stored = self.store.rule_settings(ws)
        out = []
        for rid in RULE_IDS:
            enabled, over = stored.get(rid, (True, {}))
            out.append({"rule_id": rid, "name": NAMES[rid], "enabled": enabled,
                        "params": {**self.rules[rid].DEFAULTS, **over}})
        return out

    def _paged(self, fn, ws, frm, to):
        items, cursor = [], None
        while True:
            page = fn(ws, frm, to, cursor=cursor, limit=100)
            items += page["items"]
            cursor = page.get("next_cursor")
            if not cursor:
                return items

    def run_rules(self, ws: str, t_from: datetime | None = None, t_to: datetime | None = None) -> list[FindingRow]:
        """Re-run every enabled rule over the period; a finding of the same (rule, period) is updated, not duplicated."""
        to = t_to or self.now()
        frm = t_from or to - timedelta(days=DEFAULT_PERIOD_DAYS)
        calls = [normalize_call(r) for r in self._paged(self._calls, ws, frm, to)]
        tasks = {t.id: t for t in map(normalize_task, self._paged(self._tasks, ws, frm, to))}
        prices = self._prices() or {}
        out = []
        for conf in self.list_rules(ws):
            if not conf["enabled"]:
                continue
            f = self.rules[conf["rule_id"]].detect(calls, tasks, prices, conf["params"])
            if f is None:
                continue
            existed = any(r.rule_id == f.rule_id and (r.period_start, r.period_end) == (frm, to)
                          for r in self.store.list_findings(ws, frm, to))
            row = self.store.upsert_finding(ws, f, frm, to, self.now())
            if not existed:
                self.publish("advisor.finding.created", {"workspace_id": ws, "finding_id": row.id, "rule_id": f.rule_id})
            self._propose_from(ws, row)
            out.append(row)
        return out

    def on_calls_ingested(self, name: str, payload: dict) -> None:
        if payload.get("workspace_id"):
            self.run_rules(payload["workspace_id"])

    def _propose_from(self, ws: str, row: FindingRow) -> None:
        f = row.finding
        p = self.store.by_origin(ws, "advisor", row.id)
        if p is None:
            self.submit_proposal(ws, "advisor", row.id, f.proposal["kind"], f.proposal["change"], f.p50, actor=None)
        elif p.state == "proposed":
            self.store.update_proposal(replace(p, change=f.proposal["change"], expected_savings_microusd=f.p50))

    def list_findings(self, ws: str, t_from=None, t_to=None) -> list[dict]:
        to = t_to or self.now()
        frm = t_from or to - timedelta(days=DEFAULT_PERIOD_DAYS)
        return [self.view_finding(ws, r) for r in self.store.list_findings(ws, frm, to)]

    def view_finding(self, ws, r: FindingRow) -> dict:
        f = r.finding
        p = self.store.by_origin(ws, "advisor", r.id)
        return {"id": r.id, "rule_id": r.rule_id,
                "period": {"from": r.period_start.date().isoformat(), "to": r.period_end.date().isoformat()},
                "savings": {"p10": f.p10, "p50": f.p50, "p90": f.p90, "unit": "microusd", "provenance": "ESTIMATED"},
                "savings_tokens": {"value": f.savings_tokens_p50, "unit": "tokens", "provenance": "ESTIMATED"},
                "measure": "list", "evidence_call_ids": f.evidence_call_ids, "evidence_task_ids": f.evidence_task_ids,
                "detail": f.detail, "proposal_id": p.id if p else None}

    # -- proposals -----------------------------------------------------------------------------------------
    def submit_proposal(self, ws: str, origin: str, origin_ref: str, kind: str, change: dict,
                        expected_savings: int | None = None, actor: str | None = None) -> ProposalRow:
        """The single entry for every Proposal (advisor findings, simulation, profile, later run nodes)."""
        if origin not in ORIGINS or kind not in KINDS or not isinstance(change, dict) or not origin_ref:
            raise AdvisorError("invalid_request", "invalid proposal", 422)
        now = self.now()
        p = self.store.add_proposal(ProposalRow(str(uuid.uuid4()), ws, origin, str(origin_ref), kind, dict(change),
                                                expected_savings, "proposed", None, now,
                                                now + timedelta(days=PROPOSAL_TTL_DAYS)))
        self.audit("proposal.create", actor, {"workspace_id": ws, "proposal_id": p.id, "origin": origin, "kind": kind})
        self.publish("advisor.proposal.created", {"workspace_id": ws, "proposal_id": p.id})
        return p

    def _load(self, ws, pid) -> ProposalRow:
        p = self.store.get_proposal(ws, pid)
        if p is None:
            raise AdvisorError("not_found", "proposal not found", 404)
        if p.state in ("proposed", "accepted") and p.expires_at and p.expires_at <= self.now():
            p = self.store.update_proposal(replace(p, state="expired"))
        return p

    def get_proposal(self, ws, pid) -> ProposalRow:
        return self._load(ws, pid)

    def list_proposals(self, ws, state=None) -> list[ProposalRow]:
        if state is not None and state not in STATES:
            raise AdvisorError("invalid_request", "unknown state", 422)
        for p in self.store.list_proposals(ws):
            self._load(ws, p.id)
        return self.store.list_proposals(ws, state)

    def decisions(self, pid) -> list[DecisionRow]:
        return self.store.decisions_of(pid)

    def _policy(self, role: str, kind: str) -> str | None:
        need = "admin" if kind in ADMIN_KINDS else "developer"
        return None if RANK.get(role, -1) >= RANK[need] else f"policy: {kind} requires role {need}"

    def decide(self, ws: str, user: str, role: str, pid: str, decision: str, confirm: bool = False,
               note: str = "") -> ProposalRow:
        if decision not in ("accept", "reject", "apply"):
            raise AdvisorError("invalid_request", "decision must be accept, reject or apply", 422)
        p = self._load(ws, pid)
        if decision == "apply":
            return self._apply(p, user, role, confirm, note)
        if p.state != "proposed":
            raise AdvisorError("conflict", f"proposal is {p.state}", 409)
        reason = self._policy(role, p.kind)
        if reason:
            self._record(p, user, decision, False, True, note, "proposal.blocked", {"reason": reason})
            raise AdvisorError("forbidden", reason, 403)
        p = self.store.update_proposal(replace(p, state="accepted" if decision == "accept" else "rejected"))
        self._record(p, user, decision, True, True, note, f"proposal.{decision}", {})
        self.publish("advisor.proposal.decided", {"workspace_id": ws, "proposal_id": p.id, "decision": decision})
        return p

    def _record(self, p, user, decision, policy_ok, budget_ok, note, action, extra):
        self.store.add_decision(DecisionRow(p.id, user, decision, policy_ok, budget_ok, note or "", self.now()))
        self.audit(action, user, {"workspace_id": p.workspace_id, "proposal_id": p.id, "kind": p.kind,
                                  "state": p.state, "policy_ok": policy_ok, "budget_ok": budget_ok, **extra})

    def _apply(self, p: ProposalRow, user, role, confirm, note) -> ProposalRow:
        if p.state not in ("accepted", "blocked"):
            raise AdvisorError("conflict", f"proposal is {p.state}; only an accepted proposal can be applied", 409)
        # 1. policy
        reason = self._policy(role, p.kind)
        if reason:
            return self._block(p, user, reason, False, True, note)
        # 2. budget
        scope = p.change.get("scope", "workspace")
        extra = p.change.get("extra_cost_microusd", 0)
        chk = self.quota_check(p.workspace_id, scope, int(extra or 0), p.change.get("project_id"))
        if not chk["allowed"]:
            ids = ",".join(b["budget_id"] for b in chk["blocked_by"])
            return self._block(p, user, f"budget: over limit ({ids})", True, False, note)
        # 3. explicit user confirm: refused, proposal stays acceptable
        if confirm is not True:
            self._record(p, user, "apply", True, True, note, "proposal.blocked", {"reason": "confirm_required"})
            raise AdvisorError("confirm_required", "apply needs confirm: true", 409)
        # 4. execute (export / in-platform setting only) and audit
        p = self.store.update_proposal(replace(p, state="applied", blocked_reason=None))
        self._record(p, user, "apply", True, True, note, "proposal.apply", {})
        self.publish("advisor.proposal.applied", {"workspace_id": p.workspace_id, "proposal_id": p.id})
        return p

    def _block(self, p, user, reason, policy_ok, budget_ok, note) -> ProposalRow:
        p = self.store.update_proposal(replace(p, state="blocked", blocked_reason=reason))
        self._record(p, user, "apply", policy_ok, budget_ok, note, "proposal.blocked", {"reason": reason})
        return p

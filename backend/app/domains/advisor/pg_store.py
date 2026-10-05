"""PostgreSQL store over advisor_rules / advisor_findings / proposals / proposal_decisions (docs/schema.sql)."""
from __future__ import annotations

import json

from .rules import Finding
from .service import DecisionRow, FindingRow, ProposalRow

_F = ("id, workspace_id, rule_id, detector_version, period_start, period_end, evidence_call_ids, evidence_task_ids,"
      " savings_p10_microusd, savings_p50_microusd, savings_p90_microusd, savings_tokens_p50, detail, created_at")
_P = ("id, workspace_id, origin, origin_ref, kind, change, expected_savings_microusd, state, blocked_reason,"
      " created_at, expires_at")


def _f(r) -> FindingRow:
    d = r[12] if isinstance(r[12], dict) else json.loads(r[12])
    proposal = d.pop("_proposal", {})
    f = Finding(r[2], [int(i) for i in r[6]], [str(i) for i in r[7]], int(r[8]), int(r[9]), int(r[10]), proposal, d,
                int(r[11]), int(r[3]))
    return FindingRow(str(r[0]), str(r[1]), r[2], r[4], r[5], f, r[13])


def _p(r) -> ProposalRow:
    ch = r[5] if isinstance(r[5], dict) else json.loads(r[5])
    return ProposalRow(str(r[0]), str(r[1]), r[2], r[3], r[4], ch, None if r[6] is None else int(r[6]), r[7], r[8], r[9],
                       r[10])


class PgStore:
    def __init__(self, pool) -> None:
        self.pool = pool

    def rule_settings(self, ws):
        with self.pool.connection() as c:
            rows = c.execute("SELECT rule_id, enabled, params FROM advisor_rules WHERE workspace_id=%s", (ws,)).fetchall()
        return {r[0]: (bool(r[1]), r[2] if isinstance(r[2], dict) else json.loads(r[2])) for r in rows}

    def upsert_finding(self, ws, f: Finding, start, end, now) -> FindingRow:
        detail = json.dumps({**f.detail, "_proposal": f.proposal})   # the proposal template rides in detail
        with self.pool.connection() as c:
            r = c.execute(
                "INSERT INTO advisor_findings (workspace_id, rule_id, detector_version, period_start, period_end,"
                " evidence_call_ids, evidence_task_ids, savings_p10_microusd, savings_p50_microusd, savings_p90_microusd,"
                " savings_tokens_p50, measure, detail) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'list',%s::jsonb)"
                " ON CONFLICT (workspace_id, rule_id, period_start, period_end) DO UPDATE SET"
                " detector_version=EXCLUDED.detector_version, evidence_call_ids=EXCLUDED.evidence_call_ids,"
                " evidence_task_ids=EXCLUDED.evidence_task_ids, savings_p10_microusd=EXCLUDED.savings_p10_microusd,"
                " savings_p50_microusd=EXCLUDED.savings_p50_microusd, savings_p90_microusd=EXCLUDED.savings_p90_microusd,"
                " savings_tokens_p50=EXCLUDED.savings_tokens_p50, detail=EXCLUDED.detail RETURNING " + _F,
                (ws, f.rule_id, f.detector_version, start, end, f.evidence_call_ids, f.evidence_task_ids, f.p10, f.p50,
                 f.p90, f.savings_tokens_p50, detail)).fetchone()
        return _f(r)

    def list_findings(self, ws, frm, to):
        with self.pool.connection() as c:
            rows = c.execute("SELECT " + _F + " FROM advisor_findings WHERE workspace_id=%s AND period_end>=%s"
                             " AND period_start<=%s ORDER BY created_at, rule_id", (ws, frm, to)).fetchall()
        return [_f(r) for r in rows]

    def add_proposal(self, p: ProposalRow) -> ProposalRow:
        with self.pool.connection() as c:
            r = c.execute(
                "INSERT INTO proposals (workspace_id, origin, origin_ref, kind, change, expected_savings_microusd, state,"
                " expires_at) VALUES (%s,%s,%s,%s,%s::jsonb,%s,%s,%s) RETURNING " + _P,
                (p.workspace_id, p.origin, p.origin_ref, p.kind, json.dumps(p.change), p.expected_savings_microusd,
                 p.state, p.expires_at)).fetchone()
        return _p(r)

    def get_proposal(self, ws, pid):
        with self.pool.connection() as c:
            r = c.execute("SELECT " + _P + " FROM proposals WHERE workspace_id=%s AND id::text=%s", (ws, pid)).fetchone()
        return _p(r) if r else None

    def list_proposals(self, ws, state=None):
        sql = "SELECT " + _P + " FROM proposals WHERE workspace_id=%s" + ("" if state is None else " AND state=%s")
        with self.pool.connection() as c:
            rows = c.execute(sql + " ORDER BY created_at DESC", (ws,) if state is None else (ws, state)).fetchall()
        return [_p(r) for r in rows]

    def by_origin(self, ws, origin, ref):
        with self.pool.connection() as c:
            r = c.execute("SELECT " + _P + " FROM proposals WHERE workspace_id=%s AND origin=%s AND origin_ref=%s"
                          " ORDER BY created_at LIMIT 1", (ws, origin, ref)).fetchone()
        return _p(r) if r else None

    def update_proposal(self, p: ProposalRow) -> ProposalRow:
        with self.pool.connection() as c:
            r = c.execute("UPDATE proposals SET state=%s, blocked_reason=%s, change=%s::jsonb,"
                          " expected_savings_microusd=%s WHERE id=%s RETURNING " + _P,
                          (p.state, p.blocked_reason, json.dumps(p.change), p.expected_savings_microusd, p.id)).fetchone()
        return _p(r)

    def add_decision(self, d: DecisionRow) -> None:
        with self.pool.connection() as c:
            c.execute("INSERT INTO proposal_decisions (proposal_id, decided_by, decision, policy_ok, budget_ok, note,"
                      " decided_at) VALUES (%s,%s,%s,%s,%s,%s,%s)",
                      (d.proposal_id, d.decided_by, d.decision, d.policy_ok, d.budget_ok, d.note, d.decided_at))

    def decisions_of(self, pid):
        with self.pool.connection() as c:
            rows = c.execute("SELECT proposal_id, decided_by, decision, policy_ok, budget_ok, note, decided_at FROM"
                             " proposal_decisions WHERE proposal_id::text=%s ORDER BY decided_at", (pid,)).fetchall()
        return [DecisionRow(str(r[0]), str(r[1]), r[2], r[3], r[4], r[5], r[6]) for r in rows]

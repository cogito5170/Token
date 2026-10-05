"""Profile service: profile CRUD, personal_stats refresh from usage tasks, recommendations, advisor hand-off.

Money is micro-USD (list basis) or nano-USD in stats, tokens are integers; no floats are stored.
A user's stats are only ever read with that user's id (every Store method takes `user`).
Task attribution: a usage task dict with a `user_id` belongs to that user; one without (usage tasks carry no
user yet) belongs to every user who has a profile in the workspace (single-user MVP; see report requests).
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Callable, Protocol

MIN_EVIDENCE = 5
DEFAULT_QUALITY_FLOOR = 800            # permille, used when the profile has no floor
BILLING_MODES = ("subscription", "api", "mixed")
PROFILE_DEFAULTS = {"monthly_budget_microusd": None, "task_budget_microusd": None, "quality_floor_permille": None,
                    "preferred_models": [], "preferred_providers": [], "billing_mode": None, "team_size": None,
                    "store_bodies": False}
STAT_KEY = ("task_kind", "model_id", "structure", "context_mode")


class ProfileError(Exception):
    def __init__(self, code: str, message: str, status: int = 422) -> None:
        super().__init__(message)
        self.code, self.message, self.status = code, message, status


@dataclass
class Stat:
    task_kind: str
    model_id: str
    structure: str
    context_mode: str
    tasks: int = 0
    correct: int = 0
    first_try_success: int = 0
    tokens: int = 0
    cost_list_micro: int = 0
    cost_cli_micro: int = 0
    cli_tasks: int = 0                  # tasks that have a cli cost
    tokens_per_correct: int | None = None
    cost_list_per_correct_nanousd: int | None = None
    cost_cli_per_correct_microusd: int | None = None
    version: int = 1


class Store(Protocol):
    def get_profile(self, ws: str, user: str) -> dict | None: ...
    def put_profile(self, ws: str, user: str, data: dict) -> dict: ...
    def profile_users(self, ws: str) -> list[str]: ...
    def replace_stats(self, ws: str, user: str, stats: list[Stat]) -> int: ...
    def stats(self, ws: str, user: str) -> list[Stat]: ...
    def replace_recommendations(self, ws: str, user: str, recs: list[dict]) -> None: ...
    def recommendations(self, ws: str, user: str) -> list[dict]: ...
    def set_proposal(self, ws: str, user: str, rec_id: str, proposal_id: str) -> None: ...


def _div(a: int, b: int) -> int:        # round-half-up integer division, a >= 0, b > 0
    return (2 * a + b) // (2 * b)


def compute_stats(tasks: list[dict]) -> list[Stat]:
    """Group tasks by (kind, model, structure, context_mode). Per-correct = total over ALL tasks / correct count
    (wrong attempts are paid for too); None while correct == 0."""
    groups: dict[tuple, Stat] = {}
    for t in tasks:
        if not t.get("model_primary") or not t.get("kind"):
            continue
        key = (t["kind"], t["model_primary"], t.get("structure") or "single", t.get("context_mode") or "selective")
        s = groups.setdefault(key, Stat(*key))
        s.tasks += 1
        s.tokens += int(t.get("total_tokens") or 0)
        s.cost_list_micro += int(t.get("cost_list_microusd") or 0)
        if t.get("cost_cli_microusd") is not None:
            s.cost_cli_micro += int(t["cost_cli_microusd"])
            s.cli_tasks += 1
        if t.get("outcome") == "correct":
            s.correct += 1
            if t.get("first_try_success"):
                s.first_try_success += 1
    for s in groups.values():
        if s.correct:
            s.tokens_per_correct = _div(s.tokens, s.correct)
            s.cost_list_per_correct_nanousd = _div(s.cost_list_micro * 1000, s.correct)
            if s.cli_tasks == s.tasks:   # only when every task has a measured cli cost
                s.cost_cli_per_correct_microusd = _div(s.cost_cli_micro, s.correct)
    return sorted(groups.values(), key=lambda s: (s.task_kind, s.model_id, s.structure, s.context_mode))


def recommend(stats: list[Stat], floor_permille: int | None) -> list[dict]:
    """Per task_kind: current = the most used config; candidate = a config of that kind with tasks >= 5, correct rate
    >= floor and a lower cost per correct task. The cheapest candidate wins; no candidate -> no recommendation."""
    floor = DEFAULT_QUALITY_FLOOR if floor_permille is None else floor_permille
    out = []
    for kind in sorted({s.task_kind for s in stats}):
        group = [s for s in stats if s.task_kind == kind]
        cur = max(group, key=lambda s: (s.tasks, s.model_id, s.structure, s.context_mode))
        if not cur.cost_list_per_correct_nanousd:
            continue
        best = None
        for c in group:
            if c is cur or c.tasks < MIN_EVIDENCE or not c.cost_list_per_correct_nanousd:
                continue
            if c.correct * 1000 < floor * c.tasks:
                continue
            if c.cost_list_per_correct_nanousd >= cur.cost_list_per_correct_nanousd:
                continue
            if best is None or c.cost_list_per_correct_nanousd < best.cost_list_per_correct_nanousd:
                best = c
        if best is None:
            continue
        saving = (cur.cost_list_per_correct_nanousd - best.cost_list_per_correct_nanousd) * 1000 \
            // cur.cost_list_per_correct_nanousd
        cfg = lambda s: {"task_kind": s.task_kind, "model": s.model_id, "structure": s.structure,  # noqa: E731
                         "context_mode": s.context_mode}
        label = f"{best.model_id}/{best.structure}/{best.context_mode}"
        out.append({"headline": f"당신의 {kind} 작업은 {label} 구성이 맞힌 작업당 {saving // 10}.{saving % 10}% 싸다 "
                                f"(근거 {best.tasks} 건)",
                    "current_config": cfg(cur), "recommended_config": cfg(best), "saving_permille": saving,
                    "evidence_n": best.tasks, "stats_version": best.version})
    return out


def _stat_json(s: Stat) -> dict:
    metric = lambda v, unit: {"value": v, "unit": unit, "provenance": "CALCULATED"}  # noqa: E731
    return {"task_kind": s.task_kind, "model_id": s.model_id, "structure": s.structure,
            "context_mode": s.context_mode, "tasks": s.tasks, "correct": s.correct,
            "first_try_success": s.first_try_success,
            "tokens_per_correct": metric(s.tokens_per_correct, "tokens"),
            "cost_list_per_correct": metric(None if s.cost_list_per_correct_nanousd is None
                                            else _div(s.cost_list_per_correct_nanousd, 1000), "microusd"),
            "cost_cli_per_correct": metric(s.cost_cli_per_correct_microusd, "microusd")}


def _rec_json(r: dict) -> dict:
    return {"id": r["id"], "headline": r["headline"], "current_config": r["current_config"],
            "recommended_config": r["recommended_config"],
            "saving": {"value": r["saving_permille"], "unit": "permille", "provenance": "ESTIMATED"},
            "evidence_n": r["evidence_n"], "proposal_id": r.get("proposal_id")}


def validate_profile(data: dict) -> dict:
    unknown = set(data) - set(PROFILE_DEFAULTS)
    if unknown:
        raise ProfileError("invalid_request", f"unknown fields: {', '.join(sorted(unknown))}")
    p = dict(PROFILE_DEFAULTS)
    p["preferred_models"], p["preferred_providers"] = [], []
    p.update(data)
    for k in ("monthly_budget_microusd", "task_budget_microusd", "team_size", "quality_floor_permille"):
        v = p[k]
        if v is not None and (isinstance(v, bool) or not isinstance(v, int) or v < 0):
            raise ProfileError("invalid_request", f"{k} must be a non-negative integer or null")
    if p["quality_floor_permille"] is not None and p["quality_floor_permille"] > 1000:
        raise ProfileError("invalid_request", "quality_floor_permille must be 0..1000")
    if p["billing_mode"] is not None and p["billing_mode"] not in BILLING_MODES:
        raise ProfileError("invalid_request", f"billing_mode must be one of {', '.join(BILLING_MODES)}")
    for k in ("preferred_models", "preferred_providers"):
        if not isinstance(p[k], list) or not all(isinstance(x, str) for x in p[k]):
            raise ProfileError("invalid_request", f"{k} must be a list of strings")
    if not isinstance(p["store_bodies"], bool):
        raise ProfileError("invalid_request", "store_bodies must be a boolean")
    return p


@dataclass
class ProfileService:
    store: Store
    tasks_source: Callable[[str], list[dict]]            # ws -> usage task dicts (usage.api.tasks, all pages)
    proposer: Callable[..., dict] | None = None          # advisor.api.submit_proposal(ws, origin, change, evidence)
    publish: Callable[[str, dict], object] = field(default=lambda n, p: 0)

    # -- profile ---------------------------------------------------------------------------------------------
    def get_profile(self, ws: str, user: str) -> dict:
        return self.store.get_profile(ws, user) or validate_profile({})

    def put_profile(self, ws: str, user: str, data: dict) -> dict:
        return self.store.put_profile(ws, user, validate_profile(data))

    # -- stats -----------------------------------------------------------------------------------------------
    def refresh_stats(self, ws: str, users: list[str] | None = None) -> int:
        """Recompute stats from the workspace's usage tasks; returns the number of users refreshed."""
        tasks = self.tasks_source(ws)
        targets = users if users is not None else self.store.profile_users(ws)
        for u in targets:
            mine = [t for t in tasks if t.get("user_id") in (None, u)]
            self.store.replace_stats(ws, u, compute_stats(mine))
            self.publish("profile.stats.refreshed", {"workspace_id": ws, "user_id": u})
        return len(targets)

    def on_usage_ingested(self, name: str, payload: dict) -> None:
        if payload.get("workspace_id"):
            self.refresh_stats(payload["workspace_id"])

    def stats(self, ws: str, user: str) -> list[dict]:
        return [_stat_json(s) for s in self.store.stats(ws, user)]

    # -- recommendations -------------------------------------------------------------------------------------
    def recommendations(self, ws: str, user: str) -> list[dict]:
        floor = self.get_profile(ws, user)["quality_floor_permille"]
        old = {(r["current_config"]["task_kind"], r["recommended_config"]["model"],
                r["recommended_config"]["structure"], r["recommended_config"]["context_mode"]): r
               for r in self.store.recommendations(ws, user)}
        recs = recommend(self.store.stats(ws, user), floor)
        for r in recs:
            rc = r["recommended_config"]
            prev = old.get((rc["task_kind"], rc["model"], rc["structure"], rc["context_mode"]))
            r["id"] = prev["id"] if prev else str(uuid.uuid4())
            r["proposal_id"] = prev.get("proposal_id") if prev else None
        self.store.replace_recommendations(ws, user, recs)
        return [_rec_json(r) for r in recs]

    def to_proposal(self, ws: str, user: str, rec_id: str) -> dict:
        rec = next((r for r in self.store.recommendations(ws, user) if r["id"] == rec_id), None)
        if rec is None:
            raise ProfileError("not_found", "recommendation not found", 404)
        if self.proposer is None:
            raise ProfileError("advisor_unavailable", "advisor.submit_proposal is not available", 503)
        change = {"kind": "router_tier", "from": rec["current_config"], "to": rec["recommended_config"]}
        evidence = {"stats_version": rec["stats_version"], "evidence_n": rec["evidence_n"],
                    "saving_permille": rec["saving_permille"], "provenance": "ESTIMATED"}
        proposal = self.proposer(ws, "profile", change, evidence)
        pid = str(proposal["id"]) if isinstance(proposal, dict) else str(getattr(proposal, "id"))
        self.store.set_proposal(ws, user, rec_id, pid)
        return {**_rec_json({**rec, "proposal_id": pid}), "proposal_id": pid}


class MemoryStore:
    def __init__(self) -> None:
        self.profiles: dict[tuple, dict] = {}
        self._stats: dict[tuple, list[Stat]] = {}
        self.versions: dict[tuple, int] = {}
        self.recs: dict[tuple, list[dict]] = {}

    def get_profile(self, ws, user):
        p = self.profiles.get((ws, user))
        return None if p is None else {**p, "preferred_models": list(p["preferred_models"]),
                                       "preferred_providers": list(p["preferred_providers"])}

    def put_profile(self, ws, user, data):
        self.profiles[(ws, user)] = dict(data)
        return self.get_profile(ws, user)

    def profile_users(self, ws):
        return sorted({u for (w, u) in self.profiles if w == ws})

    def replace_stats(self, ws, user, stats):
        v = self.versions[(ws, user)] = self.versions.get((ws, user), 0) + 1
        for s in stats:
            s.version = v
        self._stats[(ws, user)] = stats
        return v

    def stats(self, ws, user):
        return list(self._stats.get((ws, user), []))

    def replace_recommendations(self, ws, user, recs):
        self.recs[(ws, user)] = [dict(r) for r in recs]

    def recommendations(self, ws, user):
        return [dict(r) for r in self.recs.get((ws, user), [])]

    def set_proposal(self, ws, user, rec_id, proposal_id):
        for r in self.recs.get((ws, user), []):
            if r["id"] == rec_id:
                r["proposal_id"] = proposal_id

"""EstimationService: estimate from user history (usage.api.tasks) + global prior; record outcomes; accuracy.

Stores nothing but the featurized request (description -> sha256 + len) and numbers. Persistence is behind `store`
(dict-like in-memory default); the PG store and HTTP routes (/estimates*, /estimation/accuracy) are a follow-up.
"""
from __future__ import annotations

import itertools

from .estimator import VERSION, Evidence, estimate
from .features import Features, featurize
from .outcomes import accuracy, outcome
from .prior import load_global_prior


class EstimationError(Exception):
    status = 422


def task_to_evidence(t: dict, seq: int = 0) -> Evidence | None:
    """usage.api.tasks row -> Evidence; tasks with outcome unknown/absent are not evidence."""
    oc = t.get("outcome")
    if oc in (None, "unknown"):
        return None
    vals = {k: t[k] for k in ("input_tokens", "cache_tokens", "output_tokens", "total_tokens", "cost_list_microusd",
                              "cost_cli_microusd", "calls", "duration_ms") if t.get(k) is not None}
    return Evidence(id=str(t["id"]), seq=seq, source="user", correct=(oc == "correct"), values=vals,
                    features=Features(task_kind=t["kind"], model=t["model"], structure=t.get("structure") or "single",
                                      context_mode=t.get("context_mode") or "selective"))


class EstimationService:
    def __init__(self, tasks_fn=None, prior: list[Evidence] | None = None):
        self._tasks = tasks_fn or (lambda ws: [])
        self._prior = prior if prior is not None else load_global_prior()
        self._estimates: dict[str, dict] = {}
        self._outcomes: dict[str, dict] = {}
        self._ids = itertools.count(1)

    def create(self, ws: str, request: dict) -> dict:
        if not request.get("task_kind") or not request.get("model"):
            raise EstimationError("task_kind and model are required")
        feats, stored = featurize(request)
        user = [e for i, t in enumerate(self._tasks(ws)) if (e := task_to_evidence(t, i))]
        est = estimate(feats, user, self._prior)
        eid = f"est_{next(self._ids)}"
        row = {"id": eid, "workspace_id": ws, "request": stored, "ranges": est.ranges,
               "success_permille": est.success_permille, "provenance": est.provenance,
               "estimator_version": VERSION,
               "evidence": {"n": est.evidence_n, "basis": est.basis, "widened": est.widened,
                            "items": [{"task_id": i, "weight_permille": w, "distance_permille": d}
                                      for i, w, d in est.evidence]}}
        self._estimates[eid] = row
        return row

    def get(self, eid: str) -> dict | None:
        return self._estimates.get(eid)

    def record_outcome(self, eid: str, actual: dict) -> dict:
        row = self._estimates.get(eid)
        if row is None:
            raise EstimationError("unknown estimate")
        self._outcomes[eid] = outcome(row["ranges"], actual)
        return self._outcomes[eid]

    def accuracy(self, quantity: str = "total_tokens") -> dict:
        return accuracy(list(self._outcomes.values()), quantity)

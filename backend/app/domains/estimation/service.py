"""EstimationService: estimate from user history (usage.api.tasks) + global prior; record outcomes; accuracy.

Stores nothing but the featurized request (description -> sha256 + len) and numbers. Persistence is behind `store`
(MemoryStore here, PgStore in pg_store.py); the HTTP routes are in router.py.
"""
from __future__ import annotations

import uuid
from dataclasses import asdict
from datetime import datetime, timezone

from .estimator import VERSION, Evidence, estimate
from .features import Features, featurize
from .outcomes import accuracy, outcome
from .prior import load_global_prior

ESTIMATOR_VERSION_NO = 1  # the int the API shows; VERSION ("knn-1") is the estimator's name
KINDS = ("feature", "bug", "refactor", "docs", "other")
STRUCTURES = ("A", "B", "C", "single")
CONTEXT_MODES = ("bulk", "selective", "fresh")
MAX_DESCRIPTION = 20000
REQUIRED_QUANTITIES = ("input_tokens", "cache_tokens", "output_tokens", "cost_list_microusd", "calls")
UNITS = {"input_tokens": "tokens", "cache_tokens": "tokens", "output_tokens": "tokens", "cost_list_microusd": "microusd",
         "cost_cli_microusd": "microusd", "calls": "calls", "duration_ms": "ms"}
VIEW_NAMES = {"input_tokens": "input_tokens", "cache_tokens": "cache_tokens", "output_tokens": "output_tokens",
              "cost_list_microusd": "cost_list", "cost_cli_microusd": "cost_cli", "calls": "calls",
              "duration_ms": "duration_ms"}


class EstimationError(Exception):
    def __init__(self, message: str, status: int = 422, code: str = "invalid_request"):
        super().__init__(message)
        self.message, self.status, self.code = message, status, code


def valid_uuid(s) -> bool:
    try:
        uuid.UUID(str(s))
        return True
    except ValueError:
        return False


def validate_request(r: dict) -> None:
    """EstimateRequest of docs/api/openapi.yaml: description + task_kind + model required, enums, size limit."""
    if not isinstance(r, dict):
        raise EstimationError("request must be an object")
    desc = r.get("description")
    if not isinstance(desc, str):
        raise EstimationError("description is required")
    if len(desc) > MAX_DESCRIPTION:
        raise EstimationError(f"description is at most {MAX_DESCRIPTION} characters")
    if r.get("task_kind") not in KINDS:
        raise EstimationError("task_kind must be one of " + ", ".join(KINDS))
    if not isinstance(r.get("model"), str) or not r["model"]:
        raise EstimationError("model is required")
    for k, allowed in (("structure", STRUCTURES), ("context_mode", CONTEXT_MODES)):
        if r.get(k) is not None and r[k] not in allowed:
            raise EstimationError(f"{k} must be one of " + ", ".join(allowed))
    for k in ("repo_size_loc", "context_cap_tokens"):
        v = r.get(k)
        if v is not None and (not isinstance(v, int) or isinstance(v, bool) or v < 0):
            raise EstimationError(f"{k} must be a non-negative integer")
    if r.get("language") is not None and not isinstance(r["language"], str):
        raise EstimationError("language must be a string")


def task_to_evidence(t: dict, seq: int = 0) -> Evidence | None:
    """usage.api.tasks row -> Evidence; tasks with outcome unknown/absent are not evidence."""
    oc = t.get("outcome")
    if oc in (None, "unknown"):
        return None
    vals = {k: t[k] for k in ("input_tokens", "cache_tokens", "output_tokens", "total_tokens", "cost_list_microusd",
                              "cost_cli_microusd", "calls", "duration_ms") if t.get(k) is not None}
    model = t.get("model_primary") or t.get("model")
    if not model:
        return None
    return Evidence(id=str(t["id"]), seq=seq, source="user", correct=(oc == "correct"), values=vals,
                    features=Features(task_kind=t["kind"], model=model, structure=t.get("structure") or "single",
                                      context_mode=t.get("context_mode") or "selective"))


def _utc(dt):
    return dt if dt is None or dt.tzinfo else dt.replace(tzinfo=timezone.utc)


class MemoryStore:
    def __init__(self) -> None:
        self.rows: dict[str, dict] = {}
        self.outcomes_: dict[str, dict] = {}

    def new_id(self) -> str:
        return str(uuid.uuid4())

    def add(self, row: dict) -> dict:
        self.rows[row["id"]] = row
        return row

    def get(self, eid: str, ws: str | None = None) -> dict | None:
        r = self.rows.get(eid)
        return r if r and (ws is None or r["workspace_id"] == ws) else None

    def list(self, ws: str) -> list[dict]:
        return sorted((r for r in self.rows.values() if r["workspace_id"] == ws), key=lambda r: r["created_at"],
                      reverse=True)

    def set_outcome(self, row: dict, task_id, oc: dict, at: datetime) -> None:
        self.outcomes_[row["id"]] = {"at": at, "workspace_id": row["workspace_id"], "oc": oc}

    def outcomes(self, ws, t_from=None, t_to=None) -> list[dict]:
        return [o for o in self.outcomes_.values() if (ws is None or o["workspace_id"] == ws)
                and (t_from is None or o["at"] >= t_from) and (t_to is None or o["at"] <= t_to)]


class EstimationService:
    def __init__(self, tasks_fn=None, prior: list[Evidence] | None = None, store=None, now=None):
        self._tasks = tasks_fn or (lambda ws: [])
        self._prior = prior if prior is not None else load_global_prior()
        self.store = store or MemoryStore()
        self._now = now or (lambda: datetime.now(timezone.utc))

    def create(self, ws: str, request: dict, user_id: str | None = None) -> dict:
        validate_request(request)
        feats, stored = featurize(request)
        user = [e for i, t in enumerate(self._tasks(ws)) if (e := task_to_evidence(t, i))]
        est = estimate(feats, user, self._prior)
        ranges = dict(est.ranges)
        missing = [q for q in REQUIRED_QUANTITIES if q not in ranges]
        if missing:
            raise EstimationError("not enough evidence to estimate " + ", ".join(missing), 422, "insufficient_evidence")
        # The stored columns hold the three token parts, not a total; the total is their sum so that what is
        # persisted and what outcomes are compared against are the same numbers.
        ranges["total_tokens"] = {p: sum(ranges[q][p] for q in ("input_tokens", "cache_tokens", "output_tokens"))
                                  for p in ("p10", "p50", "p90")}
        user_ids = {e.id for e in user}
        items = [{"task_id": i, "weight_permille": w, "distance_permille": min(d, 32767)}
                 for i, w, d in est.evidence if i in user_ids and valid_uuid(i)]
        items.sort(key=lambda i: (-i["weight_permille"], i["task_id"]))  # the order a stored estimate reads back in
        row = {"id": self.store.new_id(), "workspace_id": ws, "requested_by": user_id, "request": stored,
               "features": asdict(feats), "ranges": ranges, "success_permille": est.success_permille,
               "provenance": "ESTIMATED", "estimator_version": ESTIMATOR_VERSION_NO, "estimator_name": VERSION,
               "created_at": self._now(),
               "evidence": {"n": est.evidence_n, "basis": est.basis, "widened": est.widened, "items": items}}
        return self.store.add(row)

    def get(self, ws: str, eid: str) -> dict | None:
        return self.store.get(eid, ws) if valid_uuid(eid) else None

    def list(self, ws: str) -> list[dict]:
        return self.store.list(ws)

    def record_outcome(self, eid: str, actual: dict, ws: str | None = None, task_id: str | None = None) -> dict:
        row = self.store.get(eid, ws) if valid_uuid(eid) else None
        if row is None:
            raise EstimationError("unknown estimate", 404, "not_found")
        oc = outcome(row["ranges"], actual)
        self.store.set_outcome(row, task_id, oc, self._now())
        return oc

    def accuracy(self, quantity: str = "total_tokens", ws: str | None = None, t_from=None, t_to=None) -> dict:
        return accuracy([o["oc"] for o in self.store.outcomes(ws, t_from, t_to)], quantity)

    # -- API shapes (docs/api/openapi.yaml Estimate, Accuracy) ---------------------------------------------------
    @staticmethod
    def view(row: dict) -> dict:
        def rng(q):
            r = row["ranges"].get(q)
            return None if r is None else {"p10": r["p10"], "p50": r["p50"], "p90": r["p90"], "unit": UNITS[q],
                                           "provenance": "ESTIMATED"}
        ev = row["evidence"]
        out = {VIEW_NAMES[q]: rng(q) for q in VIEW_NAMES}
        out.update(id=row["id"],
                   success_prob={"value": row["success_permille"], "unit": "permille", "provenance": "ESTIMATED"},
                   evidence={"n": ev["n"], "task_ids": [i["task_id"] for i in ev["items"]], "basis": ev["basis"]},
                   estimator={"version": row["estimator_version"], "mape_permille": row.get("mape_permille")},
                   created_at=_utc(row["created_at"]).isoformat())
        return out

    def accuracy_view(self, ws: str, t_from=None, t_to=None) -> dict:
        rows = self.store.outcomes(ws, t_from, t_to)
        ocs = [o["oc"] for o in rows]
        tok = accuracy(ocs, "total_tokens")
        ape = [o["cost_list_microusd"]["ape_permille"] for o in ocs if "cost_list_microusd" in o]
        cost_mape = round(sum(ape) / len(ape)) if ape else None  # cost has no P10-P90 verdict in the store

        def metric(v):
            return {"value": v, "unit": "permille", "provenance": "CALCULATED"}
        days: dict[str, list[int]] = {}
        for o in rows:
            if "total_tokens" in o["oc"]:
                d = _utc(o["at"]).strftime("%Y-%m-%dT00:00:00Z")
                days.setdefault(d, []).append(o["oc"]["total_tokens"]["ape_permille"])
        points = [[d, round(sum(v) / len(v))] for d, v in sorted(days.items())]
        return {"n": tok["n"], "mape_tokens": metric(tok["mape_permille"]), "mape_cost": metric(cost_mape),
                "coverage_p10_p90": metric(tok["coverage_permille"]),
                "series": {"bucket": "day", "series": [{"name": "mape_tokens", "unit": "permille",
                                                        "provenance": "CALCULATED", "points": points}]}}

"""PostgreSQL store over estimator_models, estimates, estimate_evidence, estimate_outcomes (docs/schema.sql).

Only numbers and the featurized request are written; the description text never reaches this module (`featurize`
replaced it with sha256 + length). Evidence rows exist for the workspace's own tasks only: global-prior runs are not
usage_tasks rows.
"""
from __future__ import annotations

import json
import uuid

from .service import ESTIMATOR_VERSION_NO, EstimationError

P = ("p10", "p50", "p90")
# (quantity key, column pattern for p10/p50/p90, required)
COLS = (("input_tokens", "input_tokens_{}", True), ("cache_tokens", "cache_tokens_{}", True),
        ("output_tokens", "output_tokens_{}", True), ("cost_list_microusd", "cost_list_{}_microusd", True),
        ("cost_cli_microusd", "cost_cli_{}_microusd", False), ("calls", "calls_{}", True),
        ("duration_ms", "duration_ms_{}", False))
RANGE_COLUMNS = [c.format(p) for _, c, _ in COLS for p in P]
_SELECT = ("id, workspace_id, requested_by, request, features, success_prob_permille, evidence_n, provenance, "
           "created_at, estimator_id, " + ", ".join(RANGE_COLUMNS))


def _json(v):
    return v if isinstance(v, (dict, list)) else json.loads(v)


class PgStore:
    def __init__(self, pool) -> None:
        self.pool = pool

    def new_id(self) -> str:
        return str(uuid.uuid4())

    def _model_id(self, c) -> str:
        r = c.execute("SELECT id FROM estimator_models WHERE scope='global' AND scope_id IS NULL AND version=%s "
                      "ORDER BY fitted_at LIMIT 1", (ESTIMATOR_VERSION_NO,)).fetchone()
        if r is None:
            r = c.execute("INSERT INTO estimator_models (scope, scope_id, version, params, fitted_on_n) "
                          "VALUES ('global', NULL, %s, %s, 0) RETURNING id",
                          (ESTIMATOR_VERSION_NO, json.dumps({"name": "knn-1"}))).fetchone()
        return r[0]

    def add(self, row: dict) -> dict:
        if not row.get("requested_by"):
            raise EstimationError("an estimate needs an authenticated requester", 422)
        vals = []
        for q, _, required in COLS:
            r = row["ranges"].get(q)
            if r is None and required:
                raise EstimationError(f"missing range {q}")
            vals += [None if r is None else r[p] for p in P]
        with self.pool.connection() as c:
            mid = self._model_id(c)
            c.execute(f"INSERT INTO estimates (id, workspace_id, requested_by, estimator_id, request, features, "
                      f"success_prob_permille, evidence_n, created_at, {', '.join(RANGE_COLUMNS)}) VALUES "
                      f"(%s,%s,%s,%s,%s,%s,%s,%s,%s,{', '.join(['%s'] * len(RANGE_COLUMNS))})",
                      (row["id"], row["workspace_id"], row["requested_by"], mid, json.dumps(row["request"]),
                       json.dumps(row["features"]), row["success_permille"], row["evidence"]["n"],
                       row["created_at"], *vals))
            for i in row["evidence"]["items"]:
                c.execute("INSERT INTO estimate_evidence (estimate_id, task_id, weight_permille, distance_permille) "
                          "VALUES (%s,%s,%s,%s)", (row["id"], i["task_id"], i["weight_permille"],
                                                   i["distance_permille"]))
        return row

    def _row(self, c, r) -> dict:
        ranges = {}
        vals = list(r[10:])
        for k, (q, _, _) in enumerate(COLS):
            p10, p50, p90 = vals[3 * k:3 * k + 3]
            if p50 is not None:
                ranges[q] = {"p10": int(p10), "p50": int(p50), "p90": int(p90)}
        ranges["total_tokens"] = {p: sum(ranges[q][p] for q in ("input_tokens", "cache_tokens", "output_tokens"))
                                  for p in P}
        ev = c.execute("SELECT task_id, weight_permille, distance_permille FROM estimate_evidence WHERE estimate_id=%s "
                       "ORDER BY weight_permille DESC, task_id", (r[0],)).fetchall()
        items = [{"task_id": str(t), "weight_permille": w, "distance_permille": d} for t, w, d in ev]
        n = int(r[6])
        basis = "global_prior" if not items else ("blended" if n > len(items) else "user")
        m = c.execute("SELECT version, mape_permille FROM estimator_models WHERE id=%s", (r[9],)).fetchone()
        return {"id": str(r[0]), "workspace_id": str(r[1]), "requested_by": str(r[2]), "request": _json(r[3]),
                "features": _json(r[4]), "ranges": ranges, "success_permille": int(r[5]), "provenance": r[7],
                "created_at": r[8], "estimator_version": m[0], "mape_permille": m[1],
                "evidence": {"n": n, "basis": basis, "items": items}}

    def get(self, eid: str, ws: str | None = None) -> dict | None:
        with self.pool.connection() as c:
            r = c.execute(f"SELECT {_SELECT} FROM estimates WHERE id=%s AND (%s::uuid IS NULL OR workspace_id=%s::uuid)",
                          (eid, ws, ws)).fetchone()
            return self._row(c, r) if r else None

    def list(self, ws: str) -> list[dict]:
        with self.pool.connection() as c:
            rs = c.execute(f"SELECT {_SELECT} FROM estimates WHERE workspace_id=%s ORDER BY created_at DESC, id", (ws,))
            return [self._row(c, r) for r in rs.fetchall()]

    def set_outcome(self, row: dict, task_id, oc: dict, at) -> None:
        tok, cost = oc.get("total_tokens"), oc.get("cost_list_microusd")
        if not task_id or tok is None or cost is None:
            raise EstimationError("an outcome needs task_id, actual total_tokens and cost_list_microusd")
        cli = oc.get("cost_cli_microusd")
        with self.pool.connection() as c:
            c.execute("INSERT INTO estimate_outcomes (estimate_id, task_id, actual_tokens, actual_cost_list_microusd, "
                      "actual_cost_cli_microusd, ape_tokens_permille, ape_cost_permille, within_p10_p90, recorded_at) "
                      "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (estimate_id) DO UPDATE SET "
                      "task_id=EXCLUDED.task_id, actual_tokens=EXCLUDED.actual_tokens, "
                      "actual_cost_list_microusd=EXCLUDED.actual_cost_list_microusd, "
                      "actual_cost_cli_microusd=EXCLUDED.actual_cost_cli_microusd, "
                      "ape_tokens_permille=EXCLUDED.ape_tokens_permille, ape_cost_permille=EXCLUDED.ape_cost_permille, "
                      "within_p10_p90=EXCLUDED.within_p10_p90, recorded_at=EXCLUDED.recorded_at",
                      (row["id"], task_id, tok["actual"], cost["actual"], None if cli is None else cli["actual"],
                       tok["ape_permille"], cost["ape_permille"], tok["within_p10_p90"], at))

    def outcomes(self, ws, t_from=None, t_to=None) -> list[dict]:
        with self.pool.connection() as c:
            rs = c.execute("SELECT o.recorded_at, o.actual_tokens, o.ape_tokens_permille, o.actual_cost_list_microusd, "
                           "o.ape_cost_permille, o.within_p10_p90 FROM estimate_outcomes o JOIN estimates e "
                           "ON e.id=o.estimate_id WHERE e.workspace_id=%s AND (%s::timestamptz IS NULL OR "
                           "o.recorded_at>=%s::timestamptz) AND (%s::timestamptz IS NULL OR "
                           "o.recorded_at<=%s::timestamptz) ORDER BY o.recorded_at", (ws, t_from, t_from, t_to, t_to))
            return [{"at": r[0], "workspace_id": ws,
                     "oc": {"total_tokens": {"actual": r[1], "ape_permille": r[2], "within_p10_p90": r[5]},
                            "cost_list_microusd": {"actual": r[3], "ape_permille": r[4], "within_p10_p90": None}}}
                    for r in rs.fetchall()]

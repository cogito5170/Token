"""Simulation service: what-if over past calls (consulting.md section 4).

Every result is SIMULATED and carries the assumption list plus a basis {from, to, calls, tasks, price_version,
stats_version}. Money is micro-USD, tokens are integers; float arithmetic exists only inside the Beta quantile.
Calls, tasks, personal stats, prices, ctxbudget and the advisor hand-off are injected (see wiring.py); this module
never touches another domain's tables.

How a result is built: baseline = sum of the stored `cost_list_microusd` of the calls in the period. Each assumption is
applied in order to a working copy of the calls (p50 state) and yields a (low, mid, high) cost delta in nano-USD
relative to the state before it; the deltas add up and the simulated range is baseline + summed delta (sorted, so p10
<= p50 <= p90). Costs are recomputed from tokens x price, and only the DELTA is added to the stored baseline, so an
assumption that changes nothing (model_swap between identical prices, token ratio 1) changes cost by exactly 0.
"""
from __future__ import annotations

import math
import uuid
from datetime import datetime, timezone
from typing import Callable

KINDS = ("model_swap", "context_cap", "node_count", "cache_prefix_fixed", "structure")
STRUCTURES = ("A", "B", "C", "single")
CACHE_FRACTIONS = (250, 500, 900)       # permille of the input that is a fixed prefix (R3: p10 / p50 / p90)
CACHE_WINDOW_S = 300                    # same-session calls closer than this share a prefix (R3 5-minute window)
CTX_QUALITY_PERMILLE = (-200, -100, 0)  # FINAL_TASK bulk vs selective: no difference ~ -1/5 (consulting.md 4)
CTX_HIGH_SAVING_DIV = 2                 # p90 keeps half of the p50 saving (caps lose context that must be re-read)
MIN_EVIDENCE = 3                        # fewer tasks than this widen the range (consulting.md 1.2 step 6)
WIDEN = (500, 2000)                     # permille factors applied to the low / high side when evidence is thin
Z90 = 1.2815515655446004                # normal quantile for P10 / P90 of the Beta approximation


class SimulationError(Exception):
    def __init__(self, code: str, message: str, status: int = 422) -> None:
        super().__init__(message)
        self.code, self.message, self.status = code, message, status


def _div(a: int, b: int) -> int:        # round-half-up integer division, b > 0, any sign of a
    return (2 * a + b) // (2 * b)


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse(v, name: str) -> datetime:
    try:
        dt = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
    except ValueError:
        raise SimulationError("invalid_request", f"basis.{name} must be an ISO-8601 time") from None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _is_int(v) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


def validate(assumptions, basis) -> tuple[list[dict], dict]:
    """422 on: empty / non-list assumptions, unknown kind, bad value, bad basis. Returns normalised copies."""
    if not isinstance(assumptions, list) or not assumptions:
        raise SimulationError("invalid_request", "assumptions must be a non-empty list")
    out = []
    for i, a in enumerate(assumptions):
        where = f"assumptions[{i}]"
        if not isinstance(a, dict) or a.get("kind") not in KINDS:
            raise SimulationError("invalid_request", f"{where}.kind must be one of {', '.join(KINDS)}")
        kind, value, frm = a["kind"], a.get("value"), a.get("from")
        if kind == "model_swap":
            if not isinstance(value, str) or not value or not isinstance(frm, str) or not frm:
                raise SimulationError("invalid_request", f"{where}: model_swap needs from (model) and value (model)")
        elif kind == "context_cap":
            if not _is_int(value) or value <= 0:
                raise SimulationError("invalid_request", f"{where}: value must be a positive integer (tokens)")
        elif kind == "node_count":
            if not _is_int(value) or value <= 0 or (frm is not None and (not _is_int(frm) or frm <= 0)):
                raise SimulationError("invalid_request", f"{where}: value (and from) must be positive integers")
        elif kind == "structure":
            if value not in STRUCTURES:
                raise SimulationError("invalid_request", f"{where}: value must be one of {', '.join(STRUCTURES)}")
        out.append({k: v for k, v in (("kind", kind), ("value", value), ("from", frm)) if v is not None
                    or k == "value"})
    if not isinstance(basis, dict) or "from" not in basis or "to" not in basis:
        raise SimulationError("invalid_request", "basis.from and basis.to are required")
    b = {"from": _parse(basis["from"], "from"), "to": _parse(basis["to"], "to"), "project_id": basis.get("project_id")}
    if b["from"] > b["to"]:
        raise SimulationError("invalid_request", "basis.from must not be after basis.to")
    return out, b


def beta_quantiles_permille(successes: int, n: int) -> tuple[int, int, int]:
    """P10 / P50 / P90 (permille) of Beta(s+1, n-s+1) (Laplace) by normal approximation; thin evidence is wide."""
    a, b = successes + 1, n - successes
    mean = a / (a + b)
    sd = math.sqrt(a * b / ((a + b) ** 2 * (a + b + 1)))
    q = lambda x: max(0, min(1000, round(x * 1000)))  # noqa: E731
    return q(mean - Z90 * sd), q(mean), q(mean + Z90 * sd)


class _Work:
    """Working copy of one call: tokens and model change as assumptions are applied."""

    def __init__(self, c: dict, task: dict | None) -> None:
        self.id = c.get("id")
        self.model = c["model_id"]
        self.session, self.task_id = c.get("session_id"), c.get("task_id")
        self.at = c.get("occurred_at")
        self.kind = (task or {}).get("kind")
        self.structure = (task or {}).get("structure")
        self.inp = int(c.get("input_tokens") or 0)
        self.cr = int(c.get("cache_read_tokens") or 0)
        self.cw = int(c.get("cache_write_tokens") or 0)
        self.out = int(c.get("output_tokens") or 0)
        self.ctx = int(c.get("context_tokens") or (self.inp + self.cr + self.cw))
        self.scale = 1000               # permille applied to all tokens (token-ratio effects)
        self.base_micro = int(c.get("cost_list_microusd") or 0)

    def nano(self, prices: dict, model: str | None = None, scale: int | None = None) -> int:
        p = prices[model or self.model]
        raw = self.inp * p["in"] + self.cr * p["cr"] + self.cw * p["cw5"] + self.out * p["out"]  # micro-USD/Mtok x tok
        return _div(raw * (self.scale if scale is None else scale), 1000 * 1000)   # -> nano-USD


class SimulationService:
    def __init__(self, store, calls_fn: Callable, tasks_fn: Callable, stats_fn: Callable, prices_fn: Callable,
                 proposer: Callable | None = None, publish: Callable | None = None,
                 ctxbudget: Callable | None = None, now: Callable[[], datetime] | None = None) -> None:
        self.store, self.calls_fn, self.tasks_fn, self.stats_fn = store, calls_fn, tasks_fn, stats_fn
        self.prices_fn, self.proposer, self.publish, self.ctxbudget = prices_fn, proposer, publish, ctxbudget
        self.now = now or (lambda: datetime.now(timezone.utc))

    # -- public -------------------------------------------------------------------------------------------------
    def simulate(self, ws: str, user: str, assumptions, basis) -> dict:
        assumptions, b = validate(assumptions, basis)
        prices = self.prices_fn() or {}
        if not prices:
            raise SimulationError("no_prices", "no model prices available", 503)
        calls = self.calls_fn(ws, b["from"], b["to"], b["project_id"])
        tasks = {t["id"]: t for t in self.tasks_fn(ws, b["from"], b["to"])}
        stats = self.stats_fn(ws, user) or []
        work = [_Work(c, tasks.get(c.get("task_id"))) for c in calls if c.get("model_id") in prices]
        baseline_micro = sum(w.base_micro for w in work)
        deltas, notes, used_models = [0, 0, 0], [], {w.model for w in work}
        quality = None
        for a in assumptions:
            d, note, q = getattr(self, "_" + a["kind"])(a, work, prices, stats)
            deltas = [x + y for x, y in zip(deltas, d)]
            notes.append({"kind": a["kind"], **note})
            quality = q or quality
            if a["kind"] == "model_swap":
                used_models.add(a["value"])
        lo, mid, hi = sorted(_div(x, 1000) for x in deltas)
        price_version = max((prices[m]["version"] for m in used_models if m in prices), default=None)
        if price_version is None:
            price_version = max(p["version"] for p in prices.values())
        stats_version = max((int(s["version"]) for s in stats if s.get("version") is not None), default=None)
        sim_cost = [max(0, baseline_micro + x) for x in (lo, mid, hi)]
        simulated = {"cost_list_microusd": _range(sim_cost, "microusd"),
                     "saving_microusd": _range([-x for x in (hi, mid, lo)], "microusd")}
        if quality:
            simulated["success_delta_permille"] = _range(list(quality), "permille")
        result = {"baseline": {"cost_list_microusd": {"value": baseline_micro, "unit": "microusd",
                                                      "provenance": "CALCULATED"},
                               "calls": {"value": len(work), "unit": "calls", "provenance": "MEASURED"}},
                  "simulated": simulated, "assumptions_applied": notes}
        basis_out = {"from": _iso(b["from"]), "to": _iso(b["to"]), "calls": len(work), "tasks": len(tasks),
                     "price_version": price_version, "stats_version": stats_version}
        if b["project_id"]:
            basis_out["project_id"] = b["project_id"]
        sim = {"id": str(uuid.uuid4()), "assumptions": assumptions, "basis": basis_out, "result": result,
               "provenance": "SIMULATED"}
        self.store.save(ws, user, sim)
        if self.publish:
            self.publish("simulation.simulation.completed", {"workspace_id": ws, "simulation_id": sim["id"]})
        return sim

    def get(self, ws: str, sim_id: str) -> dict:
        sim = self.store.get(ws, sim_id)
        if sim is None:
            raise SimulationError("not_found", "simulation not found", 404)
        return sim

    def to_proposal(self, ws: str, sim_id: str) -> dict:
        sim = self.get(ws, sim_id)
        if self.proposer is None:
            raise SimulationError("advisor_unavailable", "advisor.submit_proposal is not available", 503)
        change = {"kind": "simulation", "assumptions": sim["assumptions"]}
        evidence = {"simulation_id": sim["id"], "basis": sim["basis"], "result": sim["result"]["simulated"],
                    "provenance": "SIMULATED"}
        p = self.proposer(ws, "simulation", change, evidence)
        return {"simulation_id": sim["id"], "proposal_id": str(p["id"] if isinstance(p, dict) else getattr(p, "id"))}

    # -- assumptions: each returns ((low, mid, high) nano delta, note, quality range | None) -------------------------
    def _model_swap(self, a, work, prices, stats):
        frm, to = a["from"], a["value"]
        if to not in prices:
            raise SimulationError("unknown_model", f"no price for model {to}")
        affected = [w for w in work if w.model == frm]
        ratios, ev = _token_ratio(stats, frm, to)
        d = [0, 0, 0]
        for w in affected:
            r = ratios.get(w.kind) or ratios.get(None) or (1000, 1000, 1000)
            old = w.nano(prices)
            for i in range(3):
                d[i] += w.nano(prices, to, w.scale * r[i] // 1000) - old
        for w in affected:
            r = ratios.get(w.kind) or ratios.get(None) or (1000, 1000, 1000)
            w.model, w.scale = to, w.scale * r[1] // 1000
        q = _success_delta(stats, frm, to)
        note = {"from": frm, "to": to, "calls_affected": len(affected),
                "token_ratio_permille": list((ratios.get(None) or (1000, 1000, 1000))),
                "token_ratio_basis": "personal_stats" if ratios else "none (ratio 1: no stats for both models)",
                "stats_evidence_tasks": ev, "price_from": _p(prices, frm), "price_to": _p(prices, to)}
        return d, note, q

    def _context_cap(self, a, work, prices, stats):
        cap = a["value"]
        d_call, saved_pct, session_used = 0, None, False
        for w in work:
            if w.ctx > cap:
                before = w.nano(prices)
                shrink = cap * 1000 // w.ctx
                w.inp, w.cr, w.cw = w.inp * shrink // 1000, w.cr * shrink // 1000, w.cw * shrink // 1000
                w.ctx = cap
                d_call += w.nano(prices) - before
        sess_delta = None
        fn = self.ctxbudget or _default_ctxbudget()
        if fn is not None:
            by_s: dict = {}
            for w in work:
                by_s.setdefault(w.session, []).append(w)
            saved = 0
            for s, ws_ in by_s.items():
                if s is None or len(ws_) < 2:
                    continue
                r = fn([x.ctx for x in ws_], cap, cap, cap // 2)
                pct = r.get("saved_pct") if isinstance(r, dict) else getattr(r, "saved_pct", None)
                if pct:
                    saved += sum(x.nano(prices) for x in ws_) * int(round(pct * 10)) // 1000
                    session_used = True
            if session_used:
                sess_delta = -saved
        mid = d_call
        lo = min(mid, sess_delta) if sess_delta is not None else mid
        hi = mid // CTX_HIGH_SAVING_DIV if mid < 0 else mid
        note = {"cap_tokens": cap, "per_call_cap": True, "ctxbudget": "used" if session_used else
                ("no_effect" if fn is not None else "unavailable (rlo not installed; per-call cap only)")}
        return [lo, mid, hi], note, CTX_QUALITY_PERMILLE

    def _node_count(self, a, work, prices, stats):
        n, n0 = a["value"], a.get("from") or 1
        total = sum(w.nano(prices) for w in work)
        by_task: dict = {}
        for w in work:
            by_task[w.task_id] = by_task.get(w.task_id, 0) + w.base_micro
        q10, q50, q90 = _quantiles(sorted(by_task.values()))
        thin = len(by_task) < MIN_EVIDENCE
        spread = (WIDEN[0] if thin else (q10 * 1000 // q50 if q50 else 1000),
                  WIDEN[1] if thin else (q90 * 1000 // q50 if q50 else 1000))
        factor = n * 1000 // n0                                  # permille, linear in node count
        mid = _div(total * (factor - 1000), 1000)
        d = [_div(total * (factor * s // 1000 - 1000), 1000) for s in (spread[0], 1000, spread[1])]
        d[1] = mid
        for w in work:
            w.scale = w.scale * factor // 1000
        return d, {"nodes_from": n0, "nodes_to": n, "scale_permille": factor, "range_basis":
                   "widened (thin evidence)" if thin else "task cost quantiles", "tasks": len(by_task)}, None

    def _cache_prefix_fixed(self, a, work, prices, stats):
        groups: list[list[_Work]] = []
        last: dict = {}
        for w in sorted(work, key=lambda x: (str(x.session), str(x.at))):
            g = last.get(w.session)
            if g is not None and w.session is not None and _gap(g[-1], w) <= CACHE_WINDOW_S:
                g.append(w)
            else:
                g = last[w.session] = [w]
                groups.append(g)
        d, hits = [0, 0, 0], 0
        for g in groups:
            if len(g) < 2:
                continue
            first = g[0]
            for i, s in enumerate(CACHE_FRACTIONS):
                p = prices[first.model]
                d[i] += s * first.inp * (p["cw5"] - p["in"]) // 1000
            for w in g[1:]:
                if w.cr == 0 and w.inp > 0:
                    hits += 1
                    p = prices[w.model]
                    for i, s in enumerate(CACHE_FRACTIONS):
                        d[i] -= s * w.inp * (p["in"] - p["cr"]) // 1000
        d = [_div(x, 1000) for x in d]
        # a negative saving (write premium bigger than reads) is not a saving: never worse than 0 saved at p50 (R3)
        d = [min(x, 0) for x in d]
        return d, {"fractions_permille": list(CACHE_FRACTIONS), "calls_hit": hits,
                   "prefix_proxy": "same session within 300 s (prompt_prefix_hash not exposed by usage.api)"}, None

    def _structure(self, a, work, prices, stats):
        to = a["value"]
        d, hits, ratios = [0, 0, 0], 0, []
        for w in work:
            if w.kind is None or w.structure in (None, to):
                continue
            r = _cost_ratio(stats, w.kind, w.structure, to)
            if r is None:
                continue
            old, hits = w.nano(prices), hits
            for i, k in enumerate(r):
                d[i] += _div(old * (k - 1000), 1000)
            w.scale = w.scale * r[1] // 1000
            ratios.append(r[1])
        return d, {"to": to, "calls_affected": hits,
                   "ratio_basis": "personal_stats cost_list_per_correct" if hits else "none (no stats for both structures)"}, None


# -- helpers --------------------------------------------------------------------------------------------------------
def _range(v: list[int], unit: str) -> dict:
    lo, mid, hi = sorted(v)
    return {"p10": lo, "p50": mid, "p90": hi, "unit": unit, "provenance": "SIMULATED"}


def _p(prices: dict, m: str) -> dict:
    return {"model": m, "version": prices[m]["version"], "in": prices[m]["in"], "out": prices[m]["out"]}


def _quantiles(v: list[int]) -> tuple[int, int, int]:
    if not v:
        return 0, 0, 0
    at = lambda f: v[min(len(v) - 1, (len(v) - 1) * f // 100)]  # noqa: E731
    return at(10), at(50), at(90)


def _gap(a: _Work, b: _Work) -> float:
    try:
        return (datetime.fromisoformat(str(b.at).replace("Z", "+00:00"))
                - datetime.fromisoformat(str(a.at).replace("Z", "+00:00"))).total_seconds()
    except ValueError:
        return float("inf")


def _val(m) -> int | None:
    return m.get("value") if isinstance(m, dict) else m


def _rows(stats, model):
    return [s for s in stats if s["model_id"] == model and _val(s.get("tokens_per_correct")) not in (None, 0)]


def _token_ratio(stats, frm, to):
    """{task_kind | None: (low, mid, high) permille} of tokens_per_correct(to)/(from); None = all kinds pooled."""
    f_rows, t_rows = _rows(stats, frm), _rows(stats, to)
    out, per, ev = {}, [], 0
    for kind in {s["task_kind"] for s in f_rows} & {s["task_kind"] for s in t_rows}:
        f = max((s for s in f_rows if s["task_kind"] == kind), key=lambda s: s["tasks"])
        t = max((s for s in t_rows if s["task_kind"] == kind), key=lambda s: s["tasks"])
        r = _val(t["tokens_per_correct"]) * 1000 // _val(f["tokens_per_correct"])
        n = min(f["tasks"], t["tasks"])
        spread = WIDEN if n < MIN_EVIDENCE else (800, 1250)
        out[kind] = (r * spread[0] // 1000, r, r * spread[1] // 1000)
        per.append((r, f["tasks"]))
        ev += n
    if per:
        w = sum(n for _, n in per)
        mid = sum(r * n for r, n in per) // w
        out[None] = (min(v[0] for k, v in out.items() if k), mid, max(v[2] for k, v in out.items() if k))
    return out, ev


def _success_delta(stats, frm, to):
    def rate(model):
        rows = [s for s in stats if s["model_id"] == model]
        return sum(s["correct"] for s in rows), sum(s["tasks"] for s in rows)
    (fc, fn), (tc, tn) = rate(frm), rate(to)
    if fn == 0 or tn == 0:
        return None
    f, t = beta_quantiles_permille(fc, fn), beta_quantiles_permille(tc, tn)
    return (t[0] - f[2], t[1] - f[1], t[2] - f[0])


def _cost_ratio(stats, kind, frm, to):
    def pick(structure):
        rows = [s for s in stats if s["task_kind"] == kind and s["structure"] == structure
                and _val(s.get("cost_list_per_correct")) not in (None, 0)]
        return max(rows, key=lambda s: s["tasks"]) if rows else None
    f, t = pick(frm), pick(to)
    if f is None or t is None:
        return None
    r = _val(t["cost_list_per_correct"]) * 1000 // _val(f["cost_list_per_correct"])
    spread = WIDEN if min(f["tasks"], t["tasks"]) < MIN_EVIDENCE else (800, 1250)
    return r * spread[0] // 1000, r, r * spread[1] // 1000


def _default_ctxbudget():
    try:
        from rlo.ctxbudget import simulate
        return simulate
    except ImportError:
        return None

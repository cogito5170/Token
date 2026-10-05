"""R4 model_overkill: (kind, model) with >= 5 tasks, first-try success >= 90 %, a lower tier exists.

r = p_in(lower)/p_in(current); q = lower model's success (own tasks of that kind if enough, else the prior).
p50 = sum cost*(1 - r/q); p10 uses q-1/10, p90 uses q = 1. Negative -> 0 (no fire when p50 is 0).
"""
from fractions import Fraction

from . import Finding, frac, neighbour_tier, task_cost

RULE_ID = "R4"
DEFAULTS = {"min_tasks": 5, "min_first_try": "9/10", "q_lower": "9/10", "tiers": {}}


def detect(calls, tasks, prices, params):
    tiers, tc = params["tiers"], task_cost(calls)
    groups: dict = {}
    for t in tasks.values():
        if t.id in tc and t.kind and t.model:
            groups.setdefault((t.kind, t.model), []).append(t)
    best = None
    ev_calls, ev_tasks = [], []
    p = [Fraction(0)] * 3
    for (kind, model), ts in sorted(groups.items()):
        lower = neighbour_tier(model, tiers, up=False)
        if len(ts) < int(params["min_tasks"]) or lower is None or model not in prices or lower not in prices:
            continue
        known = [t for t in ts if t.first_try_success is not None]
        if not known or Fraction(sum(1 for t in known if t.first_try_success), len(known)) < frac(params["min_first_try"]):
            continue
        own = [t for t in tasks.values() if t.kind == kind and t.model == lower and t.first_try_success is not None]
        q = (Fraction(sum(1 for t in own if t.first_try_success), len(own))
             if len(own) >= int(params["min_tasks"]) else frac(params["q_lower"]))
        r = Fraction(prices[lower]["in"], prices[model]["in"])
        base = sum((tc[t.id][0] for t in ts), Fraction(0))
        for i, qq in enumerate((q - Fraction(1, 10), q, Fraction(1))):
            p[i] += max(Fraction(0), base * (1 - r / qq))
        for t in ts:
            ev_tasks.append(t.id)
            ev_calls += [c.id for c in tc[t.id][1]]
        best = best or {"kind": "router_tier", "change": {"task_kind": kind, "from_model": model, "to_model": lower,
                                                          "tier_delta": -1}}
    if not ev_calls or p[1] <= 0:
        return None
    return Finding.of(RULE_ID, ev_calls, ev_tasks, p[0], p[1], p[2], best, {"tasks": len(ev_tasks)})

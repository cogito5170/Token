"""R5 model_underkill: (kind, model) with >= 3 tasks and failure rate f >= 30 %, a higher tier exists.

C = mean cost per task, R = p_in(upper)/p_in(current), q_up = upper success (0.95 prior).
cost per correct task: current C/(1-f), upper C*R/q_up. p50 = correct * (C/(1-f) - C*R/q_up);
p10 uses q_up-1/10, p90 uses q_up = 1. Does not fire when p50 <= 0.
"""
from fractions import Fraction

from . import Finding, frac, neighbour_tier, task_cost

RULE_ID = "R5"
DEFAULTS = {"min_tasks": 3, "min_fail_rate": "3/10", "q_upper": "19/20", "tiers": {}}


def detect(calls, tasks, prices, params):
    tiers, tc = params["tiers"], task_cost(calls)
    groups: dict = {}
    for t in tasks.values():
        if t.id in tc and t.kind and t.model:
            groups.setdefault((t.kind, t.model), []).append(t)
    ev_calls, ev_tasks, prop = [], [], None
    p = [Fraction(0)] * 3
    for (kind, model), ts in sorted(groups.items()):
        upper = neighbour_tier(model, tiers, up=True)
        if len(ts) < int(params["min_tasks"]) or upper is None or model not in prices or upper not in prices:
            continue
        ok = sum(1 for t in ts if t.outcome == "correct")
        bad = sum(1 for t in ts if t.outcome == "incorrect")
        if ok + bad == 0:
            continue
        f = Fraction(bad, ok + bad)
        if f < frac(params["min_fail_rate"]) or f >= 1:
            continue
        C = sum((tc[t.id][0] for t in ts), Fraction(0)) / len(ts)
        R = Fraction(prices[upper]["in"], prices[model]["in"])
        qu = frac(params["q_upper"])
        gain = [ok * (C / (1 - f) - C * R / q) for q in (qu - Fraction(1, 10), qu, Fraction(1))]
        if gain[1] <= 0:
            continue
        for i in range(3):
            p[i] += max(Fraction(0), gain[i])
        for t in ts:
            ev_tasks.append(t.id)
            ev_calls += [c.id for c in tc[t.id][1]]
        prop = prop or {"kind": "router_tier", "change": {"task_kind": kind, "from_model": model, "to_model": upper,
                                                          "tier_delta": 1}}
    if not ev_calls:
        return None
    return Finding.of(RULE_ID, ev_calls, ev_tasks, p[0], p[1], p[2], prop, {"tasks": len(ev_tasks)})

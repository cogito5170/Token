"""R7 judge_waste: LLM calls in a judge role on tasks of a mechanically checkable kind. p50 = p90 = sum cost, p10 = p50/2."""
from fractions import Fraction

from . import Finding, cost

RULE_ID = "R7"
DEFAULTS = {"judge_roles": ["judge", "hub_judge"], "checkable_kinds": ["feature", "bug", "refactor"]}


def detect(calls, tasks, prices, params):
    hit = [c for c in calls if c.role in params["judge_roles"] and c.task in tasks
           and tasks[c.task].kind in params["checkable_kinds"] and c.cost_list_nanousd]
    if not hit:
        return None
    total = sum((cost(c) for c in hit), Fraction(0))
    return Finding.of(RULE_ID, [c.id for c in hit], {c.task for c in hit}, total / 2, total, total,
                      {"kind": "template", "change": {"move_checks_to": "ga judge",
                                                      "checks": ["tests", "mutation", "contract"]}},
                      {"judge_calls": len(hit)}, sum(c.context for c in hit))

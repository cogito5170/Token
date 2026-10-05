"""R1 bulk_injection: calls whose context exceeds T. p50 = sum cost*(ctx-C)/ctx; p10 = p50/2; p90 = sum cost*24/25."""
from fractions import Fraction

from . import Finding, cost, frac

RULE_ID = "R1"
DEFAULTS = {"T": 50000, "C": 20000}


def detect(calls, tasks, prices, params):
    T, C = int(params["T"]), int(params["C"])
    hit = [c for c in calls if c.context > T and c.cost_list_nanousd]
    if not hit:
        return None
    p50 = sum((cost(c) * (c.context - C) / c.context for c in hit), Fraction(0))
    p90 = sum((cost(c) * Fraction(24, 25) for c in hit), Fraction(0))
    saved_tokens = sum(c.context - C for c in hit)
    return Finding.of(RULE_ID, [c.id for c in hit], {c.task for c in hit if c.task}, p50 / 2, p50, p90,
                      {"kind": "context_cap", "change": {"context_cap_tokens": C, "selective_injection": True}},
                      {"threshold_tokens": T, "calls": len(hit)}, saved_tokens)

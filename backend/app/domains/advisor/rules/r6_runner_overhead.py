"""R6 runner_overhead: CLI cost / list cost >= 1.3 over >= 10 calls that have both.

S = such calls with context < 5000, overhead = sum_S (cli - list). p50 = overhead/2, p10 = overhead/4, p90 = overhead*9/10.
"""
from fractions import Fraction

from . import Finding, frac

RULE_ID = "R6"
DEFAULTS = {"min_calls": 10, "min_ratio": "13/10", "small_ctx": 5000}


def detect(calls, tasks, prices, params):
    both = [c for c in calls if c.cost_cli_microusd is not None and c.cost_list_nanousd]
    if len(both) < int(params["min_calls"]):
        return None
    cli = sum(c.cost_cli_microusd * 1000 for c in both)
    lst = sum(c.cost_list_nanousd for c in both)
    if Fraction(cli, lst) < frac(params["min_ratio"]):
        return None
    small = [c for c in both if c.context < int(params["small_ctx"])]
    over = Fraction(sum(c.cost_cli_microusd * 1000 - c.cost_list_nanousd for c in small))
    if not small or over <= 0:
        return None
    return Finding.of(RULE_ID, [c.id for c in small], {c.task for c in small if c.task}, over / 4, over / 2,
                      over * 9 / 10, {"kind": "config_export", "change": {"bare_calls": True, "batch_small_calls": 2}},
                      {"ratio_permille": int(Fraction(cli * 1000, lst)), "calls": len(both)})

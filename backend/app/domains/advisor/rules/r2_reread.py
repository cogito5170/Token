"""R2 reread: the same content hash (`<hash12>:<tokens>`) twice or more in one session.

p50 = sum over every later occurrence of tokens * cost_i/context_i; p10 = p50/2; p90 = p50.
The auxiliary ctxbudget signal (rlo.ctxbudget.simulate) is not wired (the module is not in this repo): p90 = p50.
"""
from fractions import Fraction

from . import Finding, cost

RULE_ID = "R2"
DEFAULTS = {"min_repeats": 2}


def _order(c):
    return (c.at is None, c.at, c.id)


def detect(calls, tasks, prices, params):
    min_repeats = max(2, int(params["min_repeats"]))
    seen: dict[tuple, int] = {}
    hits: dict = {}
    total, tokens = Fraction(0), 0
    for c in sorted((c for c in calls if c.session and c.content_hashes and c.context), key=_order):
        for entry in c.content_hashes:
            h, _, t = entry.partition(":")
            if not t.isdigit():
                continue
            n = seen[(c.session, h)] = seen.get((c.session, h), 0) + 1
            if n >= min_repeats:
                total += int(t) * cost(c) / c.context
                tokens += int(t)
                hits[c.id] = c
    if not hits:
        return None
    return Finding.of(RULE_ID, list(hits), {c.task for c in hits.values() if c.task}, total / 2, total, total,
                      {"kind": "config_export", "change": {"context_mode": "fresh", "state_reuse_template": "STATE.md"}},
                      {"repeated_tokens": tokens, "ctxbudget_signal": False}, tokens)

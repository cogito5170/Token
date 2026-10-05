"""R3 cache_miss: same prefix hash twice within the window, later call with cache_read = 0 and input >= min cache.

First call of a cluster is the reference; savings for share s of a call's input being the fixed prefix:
s * sum_i input_i * (p_in - p_cr) - s * input_first * (p_cw5 - p_in). s = 1/4, 1/2, 9/10. Negative -> 0.
"""
from fractions import Fraction

from . import Finding, nano

RULE_ID = "R3"
DEFAULTS = {"window_s": 300, "min_cache_tokens": {}, "default_min_cache_tokens": 1024}


def _order(c):
    return (c.at, c.id)


def detect(calls, tasks, prices, params):
    win = int(params["window_s"])
    mins = params["min_cache_tokens"]
    by_prefix: dict[str, list] = {}
    for c in calls:
        if c.prefix_hash and c.at is not None:   # NULL prefix / time is unknown, not "no match"
            by_prefix.setdefault(c.prefix_hash, []).append(c)
    evidence, firsts = [], []
    for group in by_prefix.values():
        group.sort(key=_order)
        i = 0
        while i < len(group):
            first = group[i]
            j = i + 1
            members = []
            while j < len(group) and (group[j].at - first.at).total_seconds() <= win:
                members.append(group[j])
                j += 1
            miss = [m for m in members if m.cache_read == 0
                    and m.input >= int(mins.get(m.model, params["default_min_cache_tokens"]))
                    and m.model in prices]
            if miss and first.model in prices:
                evidence += miss
                firsts.append(first)
            i = j
    if not evidence:
        return None
    out = []
    for s in (Fraction(1, 4), Fraction(1, 2), Fraction(9, 10)):
        gain = sum((s * nano(m.input, prices[m.model]["in"] - prices[m.model]["cr"]) for m in evidence), Fraction(0))
        pen = sum((s * nano(f.input, prices[f.model]["cw5"] - prices[f.model]["in"]) for f in firsts), Fraction(0))
        out.append(gain - pen)
    if out[1] <= 0:
        return None
    ids = [c.id for c in evidence]
    return Finding.of(RULE_ID, ids, {c.task for c in evidence if c.task}, *out,
                      {"kind": "template", "change": {"fix_prompt_prefix": True,
                                                      "min_cache_tokens": {m: int(mins.get(m, params["default_min_cache_tokens"]))
                                                                           for m in {c.model for c in evidence}}}},
                      {"clusters": len(firsts), "window_s": win}, sum(c.input for c in evidence) // 2)

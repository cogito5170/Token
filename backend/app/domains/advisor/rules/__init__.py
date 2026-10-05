"""Rule detectors R1-R7 (docs/consulting.md section 2): deterministic code, exact Fraction arithmetic in nano-USD.

A detector is `detect(calls, tasks, prices, params) -> Finding | None`:
  calls   list[Call]            normalized calls of the period (see below)
  tasks   dict[task_id, Task]
  prices  {model: {"in","out","cr","cw5","cw1"}}   micro-USD per Mtok  (nano-USD = tokens * price / 1000)
  params  DEFAULTS of the rule overlaid with the workspace's advisor_rules.params
Savings are computed as Fractions of nano-USD, floored once to micro-USD at the end (Finding.of).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from fractions import Fraction
from typing import Any

DETECTOR_VERSION = 1
RULE_IDS = ("R1", "R2", "R3", "R4", "R5", "R6", "R7")


@dataclass
class Call:
    id: int
    session: str | None
    task: str | None
    model: str
    role: str | None
    input: int
    cache_read: int
    cache_write: int
    output: int
    context: int
    cost_list_nanousd: int | None
    cost_cli_microusd: int | None = None
    prefix_hash: str | None = None
    content_hashes: list[str] = field(default_factory=list)
    at: datetime | None = None


@dataclass
class Task:
    id: str
    kind: str | None
    model: str | None
    outcome: str | None
    first_try_success: bool | None = None


@dataclass
class Finding:
    rule_id: str
    evidence_call_ids: list[int]
    evidence_task_ids: list[str]
    p10: int
    p50: int
    p90: int
    proposal: dict          # {"kind": ..., "change": {...}}
    detail: dict = field(default_factory=dict)
    savings_tokens_p50: int = 0
    detector_version: int = DETECTOR_VERSION

    @staticmethod
    def of(rule_id, calls, tasks, p10, p50, p90, proposal, detail=None, tokens=0):
        """Floor the exact nano-USD Fractions to micro-USD once; negative -> 0."""
        fl = lambda x: max(0, int(Fraction(x) // 1000))  # noqa: E731
        return Finding(rule_id, sorted(calls), sorted(tasks), fl(p10), fl(p50), fl(p90), proposal, detail or {},
                       int(tokens))


def frac(v: Any) -> Fraction:
    """'n/d' string, int or Fraction -> Fraction."""
    return Fraction(v) if isinstance(v, (int, Fraction)) else Fraction(str(v))


def nano(tokens: int, price_micro_per_mtok: int) -> Fraction:
    return Fraction(tokens * price_micro_per_mtok, 1000)


def cost(c: Call) -> Fraction:
    return Fraction(c.cost_list_nanousd or 0)


def task_cost(calls) -> dict:
    """task id -> (Fraction nano-USD, [calls])."""
    out: dict = {}
    for c in calls:
        if c.task:
            tot, lst = out.setdefault(c.task, [Fraction(0), []])
            out[c.task][0] = tot + cost(c)
            lst.append(c)
    return out


def neighbour_tier(model: str, tiers: dict, up: bool):
    """Nearest model above/below `model` in the tier map (None when there is none)."""
    cur = tiers.get(model)
    if cur is None:
        return None
    cand = [(t, m) for m, t in tiers.items() if (t > cur if up else t < cur)]
    if not cand:
        return None
    return (min(cand) if up else max(cand))[1]


def registry():
    from importlib import import_module
    names = {"R1": "r1_bulk_injection", "R2": "r2_reread", "R3": "r3_cache_miss", "R4": "r4_model_overkill",
             "R5": "r5_model_underkill", "R6": "r6_runner_overhead", "R7": "r7_judge_waste"}
    return {rid: import_module(f"{__name__}.{m}") for rid, m in names.items()}

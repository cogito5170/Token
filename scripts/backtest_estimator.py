#!/usr/bin/env python3
"""Backtest stub for the estimator (CMD-GC0 S6). Standard library only.

Reads the vendored FINAL_TASK results (fixtures/final_task/runs.jsonl, void rows excluded) and scores a baseline
estimator with leave-one-out: for each run, predict from the *other* valid runs of the same group
(arm, model, mode) -> fallback (mode) -> fallback (all). Point = median (P50); range = P10..P90.

Prints MAPE (mean absolute percentage error of P50) for total tokens and for quota_usd (list-price cost, integer
micro-USD), the P10-P90 coverage, and a naive global-median baseline for contrast. Later estimators must beat the
`baseline` numbers on this same script (docs/consulting.md 1.3). The last line is one JSON object for machines.

    python3 scripts/backtest_estimator.py [path/to/runs.jsonl]
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RUNS = ROOT / "fixtures" / "final_task" / "runs.jsonl"


def load(path: Path) -> list[dict]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        if r.get("void") or r.get("error") is not None:
            continue
        rows.append({
            "run_id": r["run_id"],
            "group": (r["arm"], r["model"], r["mode"]),
            "mode": r["mode"],
            "tokens": int(r["total_tokens"]),
            "cost_microusd": round(float(r["quota_usd"]) * 1_000_000),
        })
    return rows


def quantile(xs: list[int], q: float) -> int:
    """Nearest-rank on the sorted list, linear between ranks; integer result."""
    s = sorted(xs)
    if len(s) == 1:
        return s[0]
    pos = q * (len(s) - 1)
    lo = int(pos)
    hi = min(lo + 1, len(s) - 1)
    return round(s[lo] + (s[hi] - s[lo]) * (pos - lo))


def evidence(rows: list[dict], i: int) -> list[dict]:
    me = rows[i]
    others = [r for j, r in enumerate(rows) if j != i]
    for key in (lambda r: r["group"] == me["group"], lambda r: r["mode"] == me["mode"], lambda r: True):
        ev = [r for r in others if key(r)]
        if len(ev) >= 3:
            return ev
    return others


def score(rows: list[dict], predictor) -> dict:
    out = {}
    for field in ("tokens", "cost_microusd"):
        ape, covered = [], 0
        for i, r in enumerate(rows):
            ev = predictor(rows, i)
            xs = [e[field] for e in ev]
            p10, p50, p90 = quantile(xs, 0.1), quantile(xs, 0.5), quantile(xs, 0.9)
            y = r[field]
            if y <= 0:
                continue
            ape.append(abs(y - p50) / y)
            covered += p10 <= y <= p90
        out[field] = {"n": len(ape), "mape_pct": round(100 * sum(ape) / len(ape), 2),
                      "coverage_p10_p90_pct": round(100 * covered / len(ape), 1)}
    return out


def main() -> int:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else RUNS
    rows = load(path)
    if not rows:
        print("no valid runs", file=sys.stderr)
        return 1
    base = score(rows, evidence)
    naive = score(rows, lambda rs, i: [r for j, r in enumerate(rs) if j != i])
    print(f"FINAL_TASK backtest: {len(rows)} valid runs from {path.relative_to(ROOT) if path.is_relative_to(ROOT) else path}")
    for name, s in (("baseline (group median, LOO)", base), ("naive (global median, LOO)", naive)):
        t, c = s["tokens"], s["cost_microusd"]
        print(f"  {name:30s} MAPE tokens {t['mape_pct']:7.2f}%  cost {c['mape_pct']:7.2f}%   "
              f"P10-P90 coverage tokens {t['coverage_p10_p90_pct']:5.1f}%  cost {c['coverage_p10_p90_pct']:5.1f}%")
    print(json.dumps({"schema": "backtest/1", "runs": len(rows), "baseline": base, "naive": naive}, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Estimate accuracy: per-estimate outcome and MAPE / P10-P90 coverage (docs/consulting.md 1.3)."""
from __future__ import annotations


def outcome(ranges: dict, actual: dict) -> dict:
    """ape_permille (integer ‰) and within_p10_p90 per quantity, for the quantities present in both."""
    out = {}
    for q, y in actual.items():
        r = ranges.get(q)
        if r is None or y is None or y <= 0:
            continue
        out[q] = {"actual": int(y), "ape_permille": round(1000 * abs(y - r["p50"]) / y),
                  "within_p10_p90": r["p10"] <= y <= r["p90"]}
    return out


def accuracy(outcomes: list[dict], quantity: str) -> dict:
    rows = [o[quantity] for o in outcomes if quantity in o]
    if not rows:
        return {"n": 0, "mape_permille": None, "coverage_permille": None}
    return {"n": len(rows), "mape_permille": round(sum(r["ape_permille"] for r in rows) / len(rows)),
            "coverage_permille": round(1000 * sum(r["within_p10_p90"] for r in rows) / len(rows))}

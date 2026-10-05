"""Global prior from fixtures/final_task (void rows excluded). task_kind = FINAL_TASK task id, structure = arm."""
from __future__ import annotations

import json
from pathlib import Path

from .estimator import Evidence
from .features import Features

RUNS = Path(__file__).resolve().parents[4] / "fixtures" / "final_task" / "runs.jsonl"


def _family(model: str) -> str:
    return "claude"


def to_evidence(r: dict, seq: int = 0) -> Evidence:
    calls = r.get("calls") or []
    cache = sum((r.get("input_parts") or {}).get(k, 0) for k in ("cache_creation", "cache_read"))
    return Evidence(
        id=r["run_id"], seq=seq, source="global", correct=r.get("result_correct"),
        features=Features(task_kind=r["task"], model=r["model"], structure=r["arm"], context_mode=r["mode"],
                          family=_family(r["model"])),
        values={"input_tokens": int(r["input_tokens"]), "cache_tokens": int(cache),
                "output_tokens": int(r["output_tokens"]), "total_tokens": int(r["total_tokens"]),
                "cost_list_microusd": round(float(r["quota_usd"]) * 1_000_000),
                "cost_cli_microusd": round(float(r["quota_cli_usd"]) * 1_000_000),
                "calls": int(r.get("llm_calls") or len(calls))})


def load_global_prior(path: Path = RUNS) -> list[Evidence]:
    out = []
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines()):
        if not line.strip():
            continue
        r = json.loads(line)
        if r.get("void") or r.get("error") is not None:
            continue
        out.append(to_evidence(r, i))
    return out

"""Features and distance (docs/consulting.md 1.1). The description text is never kept: only its length and a hash."""
from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass

W_KIND, W_MODEL, W_STRUCT, W_MODE, W_CAP, W_LOC, W_LANG, W_DESC = 3.0, 3.0, 2.0, 4.0, 1.0, 1.0, 0.5, 0.5
TIER_MISMATCH_SAME_FAMILY = 0.5


@dataclass(frozen=True)
class Features:
    task_kind: str
    model: str
    structure: str = "single"
    context_mode: str = "selective"
    context_cap_tokens: int | None = None
    repo_size_loc: int | None = None
    language: str | None = None
    description_len: int | None = None
    family: str | None = None  # model family; same family + other model = tier mismatch (0.5 instead of 1)


def featurize(request: dict) -> tuple[Features, dict]:
    """EstimateRequest dict -> (Features, storable request). `description` becomes {sha256, len}; text is dropped."""
    desc = request.get("description")
    dlen = len(desc) if isinstance(desc, str) else None
    stored = {k: v for k, v in request.items() if k != "description"}
    if isinstance(desc, str):
        stored["description"] = {"sha256": hashlib.sha256(desc.encode("utf-8")).hexdigest(), "len": dlen}
    f = Features(task_kind=str(request["task_kind"]), model=str(request["model"]),
                 structure=str(request.get("structure") or "single"),
                 context_mode=str(request.get("context_mode") or "selective"),
                 context_cap_tokens=request.get("context_cap_tokens"), repo_size_loc=request.get("repo_size_loc"),
                 language=request.get("language"), description_len=dlen, family=request.get("family"))
    return f, stored


def _num(a, b, fn, weight) -> float:
    if a is None or b is None:
        return 0.0
    return weight * abs(fn(max(a, 1)) - fn(max(b, 1)))


def distance(a: Features, b: Features) -> float:
    d = W_KIND * (a.task_kind != b.task_kind)
    if a.model != b.model:
        d += W_MODEL * (TIER_MISMATCH_SAME_FAMILY if a.family and a.family == b.family else 1.0)
    d += W_STRUCT * (a.structure != b.structure) + W_MODE * (a.context_mode != b.context_mode)
    d += _num(a.context_cap_tokens, b.context_cap_tokens, math.log2, W_CAP)
    d += _num(a.repo_size_loc, b.repo_size_loc, math.log10, W_LOC)
    if a.language and b.language:
        d += W_LANG * (a.language != b.language)
    d += _num(a.description_len, b.description_len, math.log2, W_DESC)
    return d

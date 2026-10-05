"""Pure estimator: k-nearest evidence, weighted P10/P50/P90, Laplace success, user blend (docs/consulting.md 1.2)."""
from __future__ import annotations

from dataclasses import dataclass, field

from .features import Features, distance

K = 15
MIN_EVIDENCE = 3
BLEND_N0 = 10
QUANTITIES = ("input_tokens", "cache_tokens", "output_tokens", "total_tokens", "cost_list_microusd",
              "cost_cli_microusd", "calls", "duration_ms")
VERSION = "knn-1"


@dataclass(frozen=True)
class Evidence:
    """One finished task (user history or global prior). `values` holds integers; missing quantities are absent."""
    id: str
    features: Features
    values: dict
    correct: bool | None = None
    seq: int = 0          # higher = newer; breaks distance ties
    source: str = "user"  # "user" | "global"


@dataclass
class Estimate:
    ranges: dict = field(default_factory=dict)  # quantity -> {"p10","p50","p90"}
    success_permille: int = 500
    evidence_n: int = 0
    basis: str = "global_prior"
    widened: bool = False
    evidence: list = field(default_factory=list)  # [(id, weight_permille, distance_permille)]
    provenance: str = "ESTIMATED"
    version: str = VERSION


def weighted_quantile(pairs: list[tuple[int, float]], q: float) -> int:
    """pairs = (value, weight). Interpolates between cumulative-weight midpoints; integer result."""
    s = sorted(pairs)
    tot = sum(w for _, w in s)
    if len(s) == 1 or tot <= 0:
        return s[0][0]
    acc, pts = 0.0, []
    for v, w in s:
        pts.append((v, (acc + w / 2) / tot))
        acc += w
    if q <= pts[0][1]:
        return pts[0][0]
    for (v0, c0), (v1, c1) in zip(pts, pts[1:]):
        if q <= c1:
            return round(v0 + (v1 - v0) * (q - c0) / (c1 - c0)) if c1 > c0 else v1
    return pts[-1][0]


def nearest(target: Features, pool: list[Evidence], k: int = K) -> list[tuple[Evidence, float, float]]:
    scored = sorted(((distance(target, e.features), -e.seq, e) for e in pool), key=lambda t: (t[0], t[1]))[:k]
    return [(e, d, 1.0 / (1.0 + d)) for d, _, e in scored]


def _ranges(ev: list[tuple[Evidence, float, float]]) -> dict:
    out = {}
    for qty in QUANTITIES:
        pairs = [(int(e.values[qty]), w) for e, _, w in ev if e.values.get(qty) is not None]
        if pairs:
            out[qty] = {"p10": weighted_quantile(pairs, 0.1), "p50": weighted_quantile(pairs, 0.5),
                        "p90": weighted_quantile(pairs, 0.9)}
    return out


def _laplace_permille(ev) -> int:
    known = [(e, w) for e, _, w in ev if e.correct is not None]
    sw = sum(w for _, w in known)
    return round(1000 * (sum(w for e, w in known if e.correct) + 1) / (sw + 2))


def estimate(target: Features, user_pool: list[Evidence], global_pool: list[Evidence], k: int = K) -> Estimate:
    uev = nearest(target, user_pool, k)
    gev = nearest(target, global_pool, k)
    n_u = len(uev)
    if n_u and gev:
        lam, basis = n_u / (n_u + BLEND_N0), "blended"
        ur, gr = _ranges(uev), _ranges(gev)
        ranges = {q: {p: round(lam * ur[q][p] + (1 - lam) * gr[q][p]) for p in ("p10", "p50", "p90")}
                  if q in ur and q in gr else ur.get(q) or gr[q] for q in set(ur) | set(gr)}
        succ = round(lam * _laplace_permille(uev) + (1 - lam) * _laplace_permille(gev))
        used = uev + gev
    elif n_u:
        ranges, succ, basis, used = _ranges(uev), _laplace_permille(uev), "user", uev
    else:
        ranges, succ, basis, used = _ranges(gev), _laplace_permille(gev), "global_prior", gev
    n = len(used)
    widened = n < MIN_EVIDENCE
    if widened:
        for r in ranges.values():
            r["p10"], r["p90"] = r["p10"] // 2, r["p90"] * 2
    return Estimate(ranges={q: ranges[q] for q in QUANTITIES if q in ranges}, success_permille=succ, evidence_n=n,
                    basis=basis, widened=widened,
                    evidence=[(e.id, round(1000 * w), round(1000 * d)) for e, d, w in used])

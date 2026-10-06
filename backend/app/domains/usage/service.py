"""Usage use cases: load_calls (price + one-transaction store), chart queries, task labelling.

Store is injected so the rules test without a DB (MemoryStore here, PgStore in pg_store.py). Provenance of numbers:
tokens MEASURED, cost_list CALCULATED (price version recorded per call), cost_cli MEASURED (null = not reported,
coverage_permille says how much of the period reported it), compare ranges CALCULATED (spread over tasks).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field, replace
from datetime import date, datetime, timedelta, timezone
from typing import Callable, Protocol

from .pricing import SEED_MODELS, SEED_PRICES, ModelRow, Price, cost_nano, nano_to_micro, pick_price

KINDS = ("feature", "bug", "refactor", "docs", "other")
OUTCOMES = ("correct", "incorrect", "unknown")
STRUCTURES = ("A", "B", "C", "single")
CONTEXT_MODES = ("bulk", "selective", "fresh")
CLIENT_OF = {"claude_code": "claude_code", "ga_l0": "ga", "anthropic_export": "api", "openai_export": "api",
             "otel": "api"}
DIMS = {"structure": "structure", "model": "model_primary", "context_mode": "context_mode", "task_kind": "kind"}
DEFAULT_THRESHOLD = 50_000


class UsageError(Exception):
    """code: not_found | invalid_request"""

    def __init__(self, code: str, message: str, status: int):
        super().__init__(message)
        self.code, self.message, self.status = code, message, status


@dataclass
class CallIn:
    """One normalized call from ingestion. Token fields stay None when the source did not report them."""
    model_id: str
    provider: str
    source_kind: str
    occurred_at: datetime
    dedupe_key: str
    time_basis: str = "reported"
    call_index: int | None = None
    role: str | None = None
    input_tokens: int | None = None
    cache_read_tokens: int | None = None
    cache_write_5m_tokens: int | None = None
    cache_write_1h_tokens: int | None = None
    output_tokens: int | None = None
    thinking_tokens: int | None = None
    tool_calls: int | None = None
    latency_ms: int | None = None
    cost_cli_microusd: int | None = None
    cost_provider_microusd: int | None = None
    prompt_prefix_hash: str | None = None
    content_hashes: list[str] | None = None
    body_ref: str | None = None
    session: str | None = None   # external session id within the source
    client: str | None = None    # defaults from source_kind
    task: str | None = None      # external_ref of the task


@dataclass
class TaskIn:
    """Optional task features / outcome for the task named by CallIn.task (fixture or ga work item)."""
    kind: str = "other"
    structure: str | None = None
    context_mode: str | None = None
    context_cap_tokens: int | None = None
    repo_size_loc: int | None = None
    language: str | None = None
    model_primary: str | None = None
    node_count: int | None = None
    outcome: str = "unknown"
    outcome_source: str | None = None
    first_try_success: bool | None = None   # NULL = unknown (never False for unknown)
    user_id: str | None = None


@dataclass
class SessionIn:
    cost_cli_microusd: int | None = None  # MEASURED session total (cost-state / run.end); overrides the call sum


@dataclass
class CallRow:
    id: int
    workspace_id: str
    project_id: str | None
    source_id: str
    ingest_job_id: str
    session_id: str | None
    task_id: str | None
    source_kind: str
    provider: str
    model_id: str
    occurred_at: datetime
    time_basis: str
    call_index: int | None
    role: str | None
    input_tokens: int | None
    cache_read_tokens: int | None
    cache_write_5m_tokens: int | None
    cache_write_1h_tokens: int | None
    output_tokens: int | None
    thinking_tokens: int | None
    context_tokens: int | None
    tool_calls: int | None
    latency_ms: int | None
    cost_list_nanousd: int | None
    price_version: int | None
    cost_cli_microusd: int | None
    cost_provider_microusd: int | None
    prompt_prefix_hash: str | None
    content_hashes: list[str] | None
    dedupe_key: str
    body_ref: str | None

    @property
    def cache_write_tokens(self) -> int | None:
        return _sum(self.cache_write_5m_tokens, self.cache_write_1h_tokens)


@dataclass
class SessionRow:
    id: str
    workspace_id: str
    client: str
    external_id: str
    started_at: datetime | None = None
    ended_at: datetime | None = None
    calls: int = 0
    input_tokens: int | None = None
    cache_read_tokens: int | None = None
    cache_write_tokens: int | None = None
    output_tokens: int | None = None
    cost_list_microusd: int | None = None
    cost_cli_microusd: int | None = None


@dataclass
class TaskRow:
    id: str
    workspace_id: str
    external_ref: str | None = None
    kind: str = "other"
    structure: str | None = None
    context_mode: str | None = None
    model_primary: str | None = None
    outcome: str = "unknown"
    outcome_source: str | None = None
    started_at: datetime | None = None
    ended_at: datetime | None = None
    calls: int = 0
    input_tokens: int | None = None
    cache_read_tokens: int | None = None
    cache_write_tokens: int | None = None
    output_tokens: int | None = None
    max_call_input: int | None = None
    cost_list_nanousd: int | None = None
    cost_cli_microusd: int | None = None
    duration_ms: int | None = None
    first_try_success: bool | None = None
    user_id: str | None = None
    extra: dict = field(default_factory=dict)  # remaining TaskIn features (cap, loc, language, node_count, ...)

    @property
    def total_tokens(self) -> int | None:
        return _sum(self.input_tokens, self.cache_read_tokens, self.cache_write_tokens, self.output_tokens)


@dataclass
class DailyRow:
    day: date
    model_id: str
    source_kind: str
    calls: int
    input_tokens: int
    cache_read_tokens: int
    cache_write_tokens: int
    output_tokens: int
    cost_list_microusd: int
    cost_cli_microusd: int | None
    cli_covered_calls: int


@dataclass
class LoadResult:
    inserted: int
    duplicates: int
    rejected: list[dict]  # [{"index": i, "code": "unknown_model"}]; never carries call content
    sessions: int = 0
    tasks: int = 0


def _sum(*xs):
    v = [x for x in xs if x is not None]
    return sum(v) if v else None


class Store(Protocol):
    def models(self) -> list[ModelRow]: ...
    def prices(self) -> dict[str, list[Price]]: ...
    def load(self, ws: str, project_id: str | None, source_id: str, job_id: str, rows: list[tuple[CallIn, dict]],
             sessions: dict[str, SessionIn], tasks: dict[str, TaskIn]) -> LoadResult: ...
    def daily(self, ws: str, d_from: date, d_to: date, project: str | None) -> list[DailyRow]: ...
    def calls(self, ws: str, t_from: datetime, t_to: datetime, project: str | None, min_input: int | None = None,
              model: str | None = None, before_id: int | None = None, limit: int | None = None) -> list[CallRow]: ...
    def sessions(self, ws: str, t_from: datetime, t_to: datetime, offset: int, limit: int) -> list[SessionRow]: ...
    def tasks(self, ws: str, t_from: datetime, t_to: datetime, project: str | None, offset: int = 0,
              limit: int | None = None) -> list[TaskRow]: ...
    def task(self, ws: str, task_id: str) -> TaskRow | None: ...
    def update_task(self, ws: str, task_id: str, fields: dict) -> TaskRow | None: ...


# ---------------------------------------------------------------------------------------------------- aggregation

def aggregate_calls(rows: list[CallRow]) -> dict:
    """Totals shared by session and task rows. A total is None when no call reported that value."""
    return dict(
        calls=len(rows),
        input_tokens=_sum(*(r.input_tokens for r in rows)),
        cache_read_tokens=_sum(*(r.cache_read_tokens for r in rows)),
        cache_write_tokens=_sum(*(r.cache_write_tokens for r in rows)),
        output_tokens=_sum(*(r.output_tokens for r in rows)),
        cost_list_nanousd=_sum(*(r.cost_list_nanousd for r in rows)),
        cost_cli_microusd=_sum(*(r.cost_cli_microusd for r in rows)),
        started_at=min((r.occurred_at for r in rows), default=None),
        ended_at=max((r.occurred_at for r in rows), default=None),
    )


def daily_rows(rows: list[CallRow]) -> list[DailyRow]:
    buckets: dict[tuple, list[CallRow]] = {}
    for r in rows:
        buckets.setdefault((r.occurred_at.astimezone(timezone.utc).date(), r.model_id, r.source_kind), []).append(r)
    out = []
    for (day, model, kind), rs in sorted(buckets.items()):
        cli = [r.cost_cli_microusd for r in rs if r.cost_cli_microusd is not None]
        out.append(DailyRow(
            day, model, kind, len(rs),
            sum(r.input_tokens or 0 for r in rs), sum(r.cache_read_tokens or 0 for r in rs),
            sum(r.cache_write_tokens or 0 for r in rs), sum(r.output_tokens or 0 for r in rs),
            nano_to_micro(sum(r.cost_list_nanousd or 0 for r in rs)), sum(cli) if cli else None, len(cli)))
    return out


def percentile(sorted_vals: list[int], q: float) -> int:
    """Linear interpolation between closest ranks, rounded half up to an integer."""
    if len(sorted_vals) == 1:
        return sorted_vals[0]
    pos = (len(sorted_vals) - 1) * q
    lo = math.floor(pos)
    hi = min(lo + 1, len(sorted_vals) - 1)
    return math.floor(sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * (pos - lo) + 0.5)


def _metric(value, unit, prov, coverage=None) -> dict:
    m = {"value": value, "unit": unit, "provenance": prov}
    if coverage is not None:
        m["coverage_permille"] = coverage
    return m


def _range(vals: list[float], unit: str, prov: str) -> dict:
    s = sorted(int(math.floor(v + 0.5)) for v in vals)
    return {"p10": percentile(s, 0.1), "p50": percentile(s, 0.5), "p90": percentile(s, 0.9), "unit": unit,
            "provenance": prov}


def _bucket_start(t: datetime, bucket: str) -> datetime:
    t = t.astimezone(timezone.utc)
    if bucket == "hour":
        return t.replace(minute=0, second=0, microsecond=0)
    d = t.replace(hour=0, minute=0, second=0, microsecond=0)
    return d - timedelta(days=d.weekday()) if bucket == "week" else d


def _iso(t: datetime) -> str:
    return t.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


# ---------------------------------------------------------------------------------------------------- store (memory)

class MemoryStore:
    def __init__(self, seed: bool = True) -> None:
        self._models = list(SEED_MODELS) if seed else []
        self._prices = list(SEED_PRICES) if seed else []
        self.calls_: list[CallRow] = []
        self.sess: dict[str, SessionRow] = {}
        self.task_: dict[str, TaskRow] = {}
        self._next = 1
        self._id = 0

    def _uuid(self) -> str:
        import uuid
        return str(uuid.uuid4())

    def models(self):
        return list(self._models)

    def prices(self):
        out: dict[str, list[Price]] = {}
        for p in self._prices:
            out.setdefault(p.model_id, []).append(p)
        return out

    def load(self, ws, project_id, source_id, job_id, rows, sessions, tasks):
        seen = {(r.workspace_id, r.dedupe_key) for r in self.calls_}
        ins = dup = 0
        touched_s, touched_t = set(), set()
        for c, priced in rows:
            if (ws, c.dedupe_key) in seen:
                dup += 1
                continue
            seen.add((ws, c.dedupe_key))
            sid = tid = None
            if c.session:
                s = next((x for x in self.sess.values() if x.workspace_id == ws and x.external_id == c.session), None)
                if s is None:
                    s = SessionRow(self._uuid(), ws, c.client or CLIENT_OF.get(c.source_kind, "api"), c.session)
                    self.sess[s.id] = s
                sid = s.id
                touched_s.add(sid)
            if c.task:
                t = next((x for x in self.task_.values() if x.workspace_id == ws and x.external_ref == c.task), None)
                if t is None:
                    t = TaskRow(self._uuid(), ws, c.task)
                    self.task_[t.id] = t
                    _apply_task_in(t, tasks.get(c.task))
                tid = t.id
                touched_t.add(tid)
            self._id += 1
            self.calls_.append(CallRow(
                self._id, ws, project_id, source_id, job_id, sid, tid, c.source_kind, c.provider, c.model_id,
                c.occurred_at, c.time_basis, c.call_index, c.role, c.input_tokens, c.cache_read_tokens,
                c.cache_write_5m_tokens, c.cache_write_1h_tokens, c.output_tokens, c.thinking_tokens,
                priced["context_tokens"], c.tool_calls, c.latency_ms, priced["cost_list_nanousd"],
                priced["price_version"], c.cost_cli_microusd, c.cost_provider_microusd, c.prompt_prefix_hash,
                c.content_hashes, c.dedupe_key, c.body_ref))
            ins += 1
        for sid in touched_s:
            s, rs = self.sess[sid], [r for r in self.calls_ if r.session_id == sid]
            a = aggregate_calls(rs)
            ext = next((sessions[k] for k in sessions if self.sess[sid].external_id == k), None)
            s.started_at, s.ended_at, s.calls = a["started_at"], a["ended_at"], a["calls"]
            s.input_tokens, s.cache_read_tokens = a["input_tokens"], a["cache_read_tokens"]
            s.cache_write_tokens, s.output_tokens = a["cache_write_tokens"], a["output_tokens"]
            s.cost_list_microusd = None if a["cost_list_nanousd"] is None else nano_to_micro(a["cost_list_nanousd"])
            s.cost_cli_microusd = ext.cost_cli_microusd if ext and ext.cost_cli_microusd is not None \
                else a["cost_cli_microusd"]
        for tid in touched_t:
            t, rs = self.task_[tid], [r for r in self.calls_ if r.task_id == tid]
            a = aggregate_calls(rs)
            for k in ("calls", "input_tokens", "cache_read_tokens", "cache_write_tokens", "output_tokens",
                      "cost_list_nanousd", "cost_cli_microusd", "started_at", "ended_at"):
                setattr(t, k, a[k])
            ci = [r.context_tokens for r in rs if r.context_tokens is not None]
            t.max_call_input = max(ci) if ci else None
            t.duration_ms = int((t.ended_at - t.started_at).total_seconds() * 1000) if t.started_at else None
        return LoadResult(ins, dup, [], len(touched_s), len(touched_t))

    def _in(self, r, ws, project):
        return r.workspace_id == ws and (project is None or r.project_id == project)

    def daily(self, ws, d_from, d_to, project):
        rs = [r for r in self.calls_ if self._in(r, ws, project)
              and d_from <= r.occurred_at.astimezone(timezone.utc).date() <= d_to]
        return daily_rows(rs)

    def calls(self, ws, t_from, t_to, project, min_input=None, model=None, before_id=None, limit=None):
        rs = [r for r in self.calls_ if self._in(r, ws, project) and t_from <= r.occurred_at <= t_to
              and (min_input is None or (r.context_tokens or 0) >= min_input)
              and (model is None or r.model_id == model) and (before_id is None or r.id < before_id)]
        rs.sort(key=lambda r: -r.id)
        return rs[:limit] if limit else rs

    def sessions(self, ws, t_from, t_to, offset, limit):
        ss = [s for s in self.sess.values() if s.workspace_id == ws and s.started_at
              and t_from <= s.started_at <= t_to]
        ss.sort(key=lambda s: (s.started_at, s.id), reverse=True)
        return ss[offset:offset + limit]

    def tasks(self, ws, t_from, t_to, project, offset=0, limit=None):
        ts = [t for t in self.task_.values() if t.workspace_id == ws and t.started_at
              and t_from <= t.started_at <= t_to]
        ts.sort(key=lambda t: (t.started_at, t.id), reverse=True)
        return ts[offset:offset + limit] if limit else ts[offset:]

    def task(self, ws, task_id):
        t = self.task_.get(task_id)
        return t if t and t.workspace_id == ws else None

    def update_task(self, ws, task_id, fields):
        t = self.task(ws, task_id)
        if t:
            for k, v in fields.items():
                setattr(t, k, v)
        return t


def _apply_task_in(t: TaskRow, ti: TaskIn | None) -> None:
    if ti is None:
        return
    t.kind, t.structure, t.context_mode, t.model_primary = ti.kind, ti.structure, ti.context_mode, ti.model_primary
    t.outcome, t.outcome_source = ti.outcome, ti.outcome_source
    t.extra = {k: getattr(ti, k) for k in ("context_cap_tokens", "repo_size_loc", "language", "node_count")}
    t.first_try_success, t.user_id = ti.first_try_success, ti.user_id


# ---------------------------------------------------------------------------------------------------- service

def _noop_publish(name: str, payload: dict) -> None:
    return None


class UsageService:
    def __init__(self, store: Store, publish: Callable[[str, dict], object] = _noop_publish,
                 now: Callable[[], datetime] = lambda: datetime.now(timezone.utc)) -> None:
        self.store, self.publish, self.now = store, publish, now

    # -- models ---------------------------------------------------------------------------------------------
    def list_models(self) -> list[dict]:
        prices = self.store.prices()
        out = []
        for m in self.store.models():
            p = max(prices.get(m.id, []), key=lambda x: x.version, default=None)
            if p is None:
                continue
            out.append({"id": m.id, "provider": m.provider, "family": m.family, "tier": m.tier,
                        "min_cache_tokens": m.min_cache_tokens,
                        "price": {"version": p.version, "effective_from": p.effective_from.isoformat(),
                                  "input_per_mtok_microusd": p.input, "output_per_mtok_microusd": p.output,
                                  "cache_read_per_mtok_microusd": p.cache_read,
                                  "cache_write_5m_per_mtok_microusd": p.cache_write_5m,
                                  "cache_write_1h_per_mtok_microusd": p.cache_write_1h}})
        return out

    def price_table(self) -> dict[str, dict]:
        """{model: {in, out, cr, cw5, cw1, version}} micro-USD per Mtok, newest price version per model."""
        out = {}
        for model, ps in self.store.prices().items():
            p = max(ps, key=lambda x: x.version, default=None)
            if p is not None:
                out[model] = {"in": p.input, "out": p.output, "cr": p.cache_read, "cw5": p.cache_write_5m,
                              "cw1": p.cache_write_1h, "version": p.version}
        return out

    # -- load_calls -----------------------------------------------------------------------------------------
    def price_call(self, c: CallIn, prices: dict[str, list[Price]]) -> dict | None:
        """CALCULATED fields for one call; None when the model has no price (unknown model)."""
        p = pick_price(prices.get(c.model_id, []), c.occurred_at.astimezone(timezone.utc).date())
        if p is None:
            return None
        cw = _sum(c.cache_write_5m_tokens, c.cache_write_1h_tokens)
        return {
            "context_tokens": _sum(c.input_tokens, c.cache_read_tokens, cw),
            "cost_list_nanousd": cost_nano(p, c.input_tokens, c.cache_read_tokens, c.cache_write_5m_tokens,
                                           c.cache_write_1h_tokens, c.output_tokens),
            "price_version": p.version,
        }

    def load_calls(self, ws: str, project_id: str | None, source_id: str, ingest_job_id: str, calls: list[CallIn],
                   sessions: dict[str, SessionIn] | None = None, tasks: dict[str, TaskIn] | None = None) -> LoadResult:
        """One transaction: insert calls (idempotent by (ws, dedupe_key)), refresh session / task totals and
        usage_daily, then publish usage.calls.ingested. Calls of a model with no price are rejected by index."""
        prices = self.store.prices()
        ok, rejected = [], []
        for i, c in enumerate(calls):
            priced = self.price_call(c, prices)
            if priced is None:
                rejected.append({"index": i, "code": "unknown_model"})
            else:
                ok.append((c, priced))
        res = self.store.load(ws, project_id, source_id, ingest_job_id, ok, sessions or {}, tasks or {})
        res.rejected = rejected
        if res.inserted:
            self.publish("usage.calls.ingested", {"workspace_id": ws, "source_id": source_id,
                                                  "ingest_job_id": ingest_job_id, "inserted": res.inserted})
        return res

    # -- period helpers -------------------------------------------------------------------------------------
    def _period(self, t_from: datetime | None, t_to: datetime | None) -> tuple[datetime, datetime]:
        to = t_to or self.now()
        frm = t_from or to - timedelta(days=30)
        if frm > to:
            raise UsageError("invalid_request", "from must not be after to", 422)
        return frm, to

    # -- charts ---------------------------------------------------------------------------------------------
    def summary(self, ws, t_from=None, t_to=None, project=None) -> dict:
        from datetime import timezone
        if t_from is not None and getattr(t_from, "tzinfo", None) is not None:
            t_from = t_from.astimezone(timezone.utc)
        if t_to is not None and getattr(t_to, "tzinfo", None) is not None:
            t_to = t_to.astimezone(timezone.utc)
        frm, to = self._period(t_from, t_to)
        days = self.store.daily(ws, frm.astimezone(timezone.utc).date(), to.astimezone(timezone.utc).date(), project)
        tasks = self.store.tasks(ws, frm, to, project)
        calls = sum(d.calls for d in days)
        tokens = sum(d.input_tokens + d.cache_read_tokens + d.cache_write_tokens + d.output_tokens for d in days)
        cost_list = sum(d.cost_list_microusd for d in days)
        cli = [d.cost_cli_microusd for d in days if d.cost_cli_microusd is not None]
        cost_cli = sum(cli) if cli else None
        cov = (sum(d.cli_covered_calls for d in days) * 1000 // calls) if calls else 0
        correct = sum(1 for t in tasks if t.outcome == "correct")
        cli_tasks = [t.cost_cli_microusd for t in tasks if t.outcome == "correct" and t.cost_cli_microusd is not None]
        list_tasks = [t.cost_list_nanousd for t in tasks if t.outcome == "correct" and t.cost_list_nanousd is not None]
        tiles = {
            "total_tokens": _metric(tokens if calls else None, "tokens", "MEASURED"),
            "cost_list": _metric(cost_list if calls else None, "microusd", "CALCULATED"),
            "cost_cli": _metric(cost_cli, "microusd", "MEASURED", cov),
            "correct_tasks": _metric(correct, "tasks", "CALCULATED"),
            "cost_list_per_correct": _metric(nano_to_micro(sum(list_tasks)) // correct if correct and list_tasks
                                             else None, "microusd", "CALCULATED"),
            "cost_cli_per_correct": _metric(sum(cli_tasks) // correct if correct and cli_tasks else None,
                                            "microusd", "MEASURED", cov),
            "budget_use": _metric(None, "permille", "CALCULATED"),  # filled by quota (budgets); unknown here
        }
        by_day: dict[date, list[DailyRow]] = {}
        for d in days:
            by_day.setdefault(d.day, []).append(d)
        pts = lambda f: [[_iso(datetime(k.year, k.month, k.day, tzinfo=timezone.utc)), f(v)]  # noqa: E731
                         for k, v in sorted(by_day.items())]
        clis = lambda v: sum(x.cost_cli_microusd for x in v if x.cost_cli_microusd is not None) \
            if any(x.cost_cli_microusd is not None for x in v) else None  # noqa: E731
        trend = {"bucket": "day", "series": [
            {"name": "total_tokens", "unit": "tokens", "provenance": "MEASURED", "points": pts(
                lambda v: sum(x.input_tokens + x.cache_read_tokens + x.cache_write_tokens + x.output_tokens
                              for x in v))},
            {"name": "cost_list", "unit": "microusd", "provenance": "CALCULATED",
             "points": pts(lambda v: sum(x.cost_list_microusd for x in v))},
            {"name": "cost_cli", "unit": "microusd", "provenance": "MEASURED", "points": pts(clis)},
        ]}
        return {"period": {"from": frm.date().isoformat(), "to": to.date().isoformat()}, "tiles": tiles,
                "trend": trend}

    def token_series(self, ws, t_from=None, t_to=None, project=None, bucket="day", group_by="none") -> dict:
        if bucket not in ("hour", "day", "week") or group_by not in ("none", "model", "source_kind"):
            raise UsageError("invalid_request", "bad bucket or group_by", 422)
        frm, to = self._period(t_from, t_to)
        acc: dict[tuple, dict[datetime, list[int]]] = {}
        if bucket == "hour":  # finer than a day: read the calls
            items = [(r.occurred_at, r.model_id, r.source_kind, r.input_tokens or 0, r.cache_read_tokens or 0,
                      r.cache_write_tokens or 0, r.output_tokens or 0)
                     for r in self.store.calls(ws, frm, to, project)]
        else:
            items = [(datetime(d.day.year, d.day.month, d.day.day, tzinfo=timezone.utc), d.model_id, d.source_kind,
                      d.input_tokens, d.cache_read_tokens, d.cache_write_tokens, d.output_tokens)
                     for d in self.store.daily(ws, frm.astimezone(timezone.utc).date(),
                                               to.astimezone(timezone.utc).date(), project)]
        for t, model, kind, *vals in items:
            g = {"none": "", "model": model, "source_kind": kind}[group_by]
            b = acc.setdefault((g,), {}).setdefault(_bucket_start(t, bucket), [0, 0, 0, 0])
            for i, v in enumerate(vals):
                b[i] += v
        series = []
        for (g,), buckets in sorted(acc.items()):
            for i, name in enumerate(("input", "cache_read", "cache_write", "output")):
                series.append({"name": f"{g}:{name}" if g else name, "unit": "tokens", "provenance": "MEASURED",
                               "points": [[_iso(t), v[i]] for t, v in sorted(buckets.items())]})
        return {"bucket": bucket, "series": series}

    def call_size(self, ws, t_from=None, t_to=None, project=None, threshold=DEFAULT_THRESHOLD) -> dict:
        frm, to = self._period(t_from, t_to)
        rows = [r for r in self.store.calls(ws, frm, to, project) if r.context_tokens is not None]
        counts: dict[int, int] = {}
        for r in rows:
            k = -1 if r.context_tokens < 1 else r.context_tokens.bit_length() - 1  # log2 bin [2^k, 2^(k+1))
            counts[k] = counts.get(k, 0) + 1
        bins = [{"lo": 0 if k < 0 else 2 ** k, "hi": 1 if k < 0 else 2 ** (k + 1), "count": n}
                for k, n in sorted(counts.items())]
        outliers = [{"call_id": r.id, "context_tokens": r.context_tokens, "model_id": r.model_id,
                     "occurred_at": _iso(r.occurred_at)}
                    for r in sorted(rows, key=lambda r: -r.context_tokens) if r.context_tokens >= threshold]
        return {"unit": "tokens", "provenance": "CALCULATED", "threshold": threshold, "bins": bins,
                "outliers": outliers}

    def compare(self, ws, dims: list[str], t_from=None, t_to=None, project=None) -> dict:
        """Group tasks by `dims`. Per group: tokens / list cost / cli cost per correct task as P10/P50/P90 over the
        group's tasks, each task's value divided by the group accuracy (expected cost to get one correct). Groups
        without a correct task are left out (a per-correct figure is undefined there)."""
        if not dims or any(d not in DIMS for d in dims):
            raise UsageError("invalid_request", "dims must be from " + ",".join(DIMS), 422)
        frm, to = self._period(t_from, t_to)
        groups: dict[tuple, list[TaskRow]] = {}
        for t in self.store.tasks(ws, frm, to, project):
            groups.setdefault(tuple(getattr(t, DIMS[d]) or "unknown" for d in dims), []).append(t)
        out = []
        for key, ts in sorted(groups.items()):
            correct = sum(1 for t in ts if t.outcome == "correct")
            if not correct:
                continue
            acc = correct / len(ts)
            g = {"key": dict(zip(dims, key)), "tasks": len(ts), "correct": correct,
                 "accuracy": _metric(correct * 1000 // len(ts), "permille", "CALCULATED")}
            tok = [t.total_tokens / acc for t in ts if t.total_tokens is not None]
            lst = [t.cost_list_nanousd / 1000 / acc for t in ts if t.cost_list_nanousd is not None]
            cli = [t.cost_cli_microusd / acc for t in ts if t.cost_cli_microusd is not None]
            g["tokens_per_correct"] = _range(tok, "tokens", "CALCULATED") if tok else None
            g["cost_list_per_correct"] = _range(lst, "microusd", "CALCULATED") if lst else None
            if cli:
                g["cost_cli_per_correct"] = _range(cli, "microusd", "MEASURED")
            out.append({k: v for k, v in g.items() if v is not None})
        return {"dims": dims, "groups": out}

    # -- pages ----------------------------------------------------------------------------------------------
    def call_page(self, ws, t_from=None, t_to=None, project=None, cursor=None, limit=100, min_input=None,
                  model=None) -> dict:
        frm, to = self._period(t_from, t_to)
        before = _cursor(cursor)
        rows = self.store.calls(ws, frm, to, project, min_input, model, before, limit + 1)
        return {"items": [_call(r) for r in rows[:limit]],
                "next_cursor": str(rows[limit - 1].id) if len(rows) > limit else None}

    def session_page(self, ws, t_from=None, t_to=None, cursor=None, limit=100) -> dict:
        frm, to = self._period(t_from, t_to)
        off = _cursor(cursor) or 0
        rows = self.store.sessions(ws, frm, to, off, limit + 1)
        return {"items": [_session(s) for s in rows[:limit]], "next_cursor": str(off + limit) if len(rows) > limit
                else None}

    def task_page(self, ws, t_from=None, t_to=None, cursor=None, limit=100) -> dict:
        frm, to = self._period(t_from, t_to)
        off = _cursor(cursor) or 0
        rows = self.store.tasks(ws, frm, to, None, off, limit + 1)
        return {"items": [_task(t) for t in rows[:limit]], "next_cursor": str(off + limit) if len(rows) > limit
                else None}

    # -- task labelling -------------------------------------------------------------------------------------
    def update_task(self, ws: str, actor: str, task_id: str, kind=None, outcome=None, structure=None,
                    context_mode=None) -> dict:
        checks = (("kind", kind, KINDS), ("outcome", outcome, OUTCOMES), ("structure", structure, STRUCTURES),
                  ("context_mode", context_mode, CONTEXT_MODES))
        fields = {}
        for name, v, allowed in checks:
            if v is not None:
                if v not in allowed:
                    raise UsageError("invalid_request", f"{name} must be one of {', '.join(allowed)}", 422)
                fields[name] = v
        t = self.store.task(ws, task_id)
        if t is None:
            raise UsageError("not_found", "task not found", 404)
        previous = t.outcome
        if "outcome" in fields:
            fields["outcome_source"] = "user"
        t = self.store.update_task(ws, task_id, fields)
        if "outcome" in fields and fields["outcome"] != previous:
            self.publish("usage.task.outcome_set", {"workspace_id": ws, "task_id": task_id, "outcome": t.outcome,
                                                    "previous": previous, "actor": actor})
        return _task(t)


def _cursor(c: str | None) -> int | None:
    if c in (None, ""):
        return None
    try:
        v = int(c)
    except ValueError:
        raise UsageError("invalid_request", "bad cursor", 422) from None
    if v < 0:
        raise UsageError("invalid_request", "bad cursor", 422)
    return v


def _micro(nano):
    return None if nano is None else nano_to_micro(nano)


def _call(r: CallRow) -> dict:
    return {"id": r.id, "occurred_at": _iso(r.occurred_at), "time_basis": r.time_basis, "model_id": r.model_id,
            "provider": r.provider, "source_kind": r.source_kind, "role": r.role, "session_id": r.session_id,
            "task_id": r.task_id, "input_tokens": r.input_tokens, "cache_read_tokens": r.cache_read_tokens,
            "cache_write_tokens": r.cache_write_tokens, "output_tokens": r.output_tokens,
            "context_tokens": r.context_tokens, "cost_list_microusd": _micro(r.cost_list_nanousd),
            "cost_list_nanousd": r.cost_list_nanousd, "cost_cli_microusd": r.cost_cli_microusd,
            "prompt_prefix_hash": r.prompt_prefix_hash, "content_hashes": r.content_hashes}


def _session(s: SessionRow) -> dict:
    return {"id": s.id, "client": s.client, "started_at": s.started_at and _iso(s.started_at),
            "ended_at": s.ended_at and _iso(s.ended_at), "calls": s.calls,
            "cost_list_microusd": s.cost_list_microusd, "cost_cli_microusd": s.cost_cli_microusd}


def _task(t: TaskRow) -> dict:
    return {"id": t.id, "external_ref": t.external_ref, "kind": t.kind, "structure": t.structure,
            "context_mode": t.context_mode, "model_primary": t.model_primary, "outcome": t.outcome, "calls": t.calls,
            "total_tokens": t.total_tokens, "cost_list_microusd": _micro(t.cost_list_nanousd),
            "cost_cli_microusd": t.cost_cli_microusd, "first_try_success": t.first_try_success,
            "user_id": t.user_id}

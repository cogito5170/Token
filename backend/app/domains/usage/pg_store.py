"""PostgreSQL Store over models / model_prices / usage_* (docs/schema.sql). Pool is injected.

load() is one transaction: insert calls (ON CONFLICT (workspace_id, dedupe_key) DO NOTHING), then recompute the
touched sessions, tasks and usage_daily buckets from usage_calls, so a reload changes nothing.
"""
from __future__ import annotations

from datetime import date, timezone

from .pricing import SEED_MODELS, SEED_PRICES, ModelRow, Price
from .service import (CLIENT_OF, CallRow, DailyRow, LoadResult, SessionRow, TaskIn, TaskRow)

CALL_COLS = ("id, workspace_id, project_id, source_id, ingest_job_id, session_id, task_id, source_kind, provider, "
             "model_id, occurred_at, time_basis, call_index, role, input_tokens, cache_read_tokens, "
             "cache_write_5m_tokens, cache_write_1h_tokens, output_tokens, thinking_tokens, context_tokens, "
             "tool_calls, latency_ms, cost_list_nanousd, price_version, cost_cli_microusd, cost_provider_microusd, "
             "prompt_prefix_hash, content_hashes, dedupe_key, body_ref")
TASK_COLS = ("id, workspace_id, external_ref, kind, structure, context_mode, model_primary, outcome, outcome_source, "
             "started_at, ended_at, calls, input_tokens, cache_read_tokens, cache_write_tokens, output_tokens, "
             "max_call_input, cost_list_nanousd, cost_cli_microusd, duration_ms")
SESSION_COLS = ("id, workspace_id, client, external_id, started_at, ended_at, calls, input_tokens, cache_read_tokens, "
                "cache_write_tokens, output_tokens, cost_list_microusd, cost_cli_microusd")
TASK_FIELDS = ("kind", "outcome", "outcome_source", "structure", "context_mode")


def _s(x):
    return None if x is None else str(x)


def _call(r) -> CallRow:
    r = list(r)
    for i in (1, 2, 3, 4, 5, 6):
        r[i] = _s(r[i])
    return CallRow(*r)


def seed(pool) -> None:
    """Fill models / model_prices when missing (idempotent). Existing prices are never changed."""
    with pool.connection() as c:
        for m in SEED_MODELS:
            c.execute("INSERT INTO models (id, provider, family, tier, min_cache_tokens, display_name) "
                      "VALUES (%s,%s,%s,%s,%s,%s) ON CONFLICT (id) DO NOTHING",
                      (m.id, m.provider, m.family, m.tier, m.min_cache_tokens, m.display_name))
        for p in SEED_PRICES:
            c.execute("INSERT INTO model_prices (model_id, version, effective_from, input_per_mtok_microusd, "
                      "output_per_mtok_microusd, cache_read_per_mtok_microusd, cache_write_5m_per_mtok_microusd, "
                      "cache_write_1h_per_mtok_microusd, source_note) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) "
                      "ON CONFLICT (model_id, version) DO NOTHING",
                      (p.model_id, p.version, p.effective_from, p.input, p.output, p.cache_read, p.cache_write_5m,
                       p.cache_write_1h, p.source_note))


class PgStore:
    def __init__(self, pool) -> None:
        self.pool = pool

    def models(self):
        with self.pool.connection() as c:
            rows = c.execute("SELECT id, provider, family, tier, min_cache_tokens, display_name FROM models "
                             "ORDER BY tier, id").fetchall()
        return [ModelRow(*r) for r in rows]

    def prices(self):
        out: dict[str, list[Price]] = {}
        with self.pool.connection() as c:
            rows = c.execute("SELECT model_id, version, effective_from, input_per_mtok_microusd, "
                             "output_per_mtok_microusd, cache_read_per_mtok_microusd, cache_write_5m_per_mtok_microusd, "
                             "cache_write_1h_per_mtok_microusd, source_note FROM model_prices").fetchall()
        for r in rows:
            out.setdefault(r[0], []).append(Price(*r))
        return out

    def load(self, ws, project_id, source_id, job_id, rows, sessions, tasks):
        ins = dup = 0
        with self.pool.connection() as c:  # one transaction (commits on exit, rolls back on error)
            sess_ids: dict[str, str] = {}
            task_ids: dict[str, str] = {}
            for call, priced in rows:
                sid = tid = None
                if call.session:
                    if call.session not in sess_ids:
                        sess_ids[call.session] = str(c.execute(
                            "INSERT INTO usage_sessions (workspace_id, project_id, source_id, client, external_id) "
                            "VALUES (%s,%s,%s,%s,%s) ON CONFLICT (workspace_id, source_id, external_id) "
                            "DO UPDATE SET external_id = EXCLUDED.external_id RETURNING id",
                            (ws, project_id, source_id, call.client or CLIENT_OF.get(call.source_kind, "api"),
                             call.session)).fetchone()[0])
                    sid = sess_ids[call.session]
                if call.task:
                    if call.task not in task_ids:
                        task_ids[call.task] = self._task_id(c, ws, project_id, call.task, tasks.get(call.task))
                    tid = task_ids[call.task]
                n = c.execute(
                    "INSERT INTO usage_calls (workspace_id, project_id, source_id, ingest_job_id, session_id, task_id, "
                    "source_kind, provider, model_id, occurred_at, time_basis, call_index, role, input_tokens, "
                    "cache_read_tokens, cache_write_5m_tokens, cache_write_1h_tokens, output_tokens, thinking_tokens, "
                    "context_tokens, tool_calls, latency_ms, cost_list_nanousd, price_version, cost_cli_microusd, "
                    "cost_provider_microusd, prompt_prefix_hash, content_hashes, dedupe_key, body_ref) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) "
                    "ON CONFLICT (workspace_id, dedupe_key) DO NOTHING",
                    (ws, project_id, source_id, job_id, sid, tid, call.source_kind, call.provider, call.model_id,
                     call.occurred_at, call.time_basis, call.call_index, call.role, call.input_tokens,
                     call.cache_read_tokens, call.cache_write_5m_tokens, call.cache_write_1h_tokens,
                     call.output_tokens, call.thinking_tokens, priced["context_tokens"], call.tool_calls,
                     call.latency_ms, priced["cost_list_nanousd"], priced["price_version"], call.cost_cli_microusd,
                     call.cost_provider_microusd, call.prompt_prefix_hash, call.content_hashes, call.dedupe_key,
                     call.body_ref)).rowcount
                ins, dup = ins + n, dup + (1 - n)
            for sid in sess_ids.values():
                self._refresh_session(c, sid, sessions, ws)
            for tid in task_ids.values():
                self._refresh_task(c, tid)
            self._refresh_daily(c, ws, project_id, rows)
        return LoadResult(ins, dup, [], len(sess_ids), len(task_ids))

    @staticmethod
    def _task_id(c, ws, project_id, ref, ti) -> str:
        r = c.execute("SELECT id FROM usage_tasks WHERE workspace_id=%s AND external_ref=%s", (ws, ref)).fetchone()
        if r:
            return str(r[0])
        ti = ti or TaskIn()
        return str(c.execute(
            "INSERT INTO usage_tasks (workspace_id, project_id, external_ref, kind, structure, context_mode, "
            "context_cap_tokens, repo_size_loc, language, model_primary, node_count, outcome, outcome_source, "
            "first_try_success) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
            (ws, project_id, ref, ti.kind, ti.structure, ti.context_mode, ti.context_cap_tokens, ti.repo_size_loc,
             ti.language, ti.model_primary, ti.node_count, ti.outcome, ti.outcome_source,
             ti.first_try_success)).fetchone()[0])

    @staticmethod
    def _refresh_session(c, sid, sessions, ws) -> None:
        ext = c.execute("SELECT external_id FROM usage_sessions WHERE id=%s", (sid,)).fetchone()[0]
        given = sessions.get(ext)
        c.execute(
            "UPDATE usage_sessions s SET started_at=a.t0, ended_at=a.t1, calls=a.n, input_tokens=a.i, "
            "cache_read_tokens=a.cr, cache_write_tokens=a.cw, output_tokens=a.o, "
            "cost_list_microusd=CASE WHEN a.nano IS NULL THEN NULL ELSE (a.nano + 500) / 1000 END, "
            "cost_cli_microusd=COALESCE(%s, a.cli) FROM ("
            "SELECT min(occurred_at) t0, max(occurred_at) t1, count(*) n, sum(input_tokens) i, "
            "sum(cache_read_tokens) cr, sum(COALESCE(cache_write_5m_tokens,0)+COALESCE(cache_write_1h_tokens,0)) "
            "FILTER (WHERE cache_write_5m_tokens IS NOT NULL OR cache_write_1h_tokens IS NOT NULL) cw, "
            "sum(output_tokens) o, sum(cost_list_nanousd) nano, sum(cost_cli_microusd) cli "
            "FROM usage_calls WHERE session_id=%s) a WHERE s.id=%s",
            (given.cost_cli_microusd if given else None, sid, sid))

    @staticmethod
    def _refresh_task(c, tid) -> None:
        c.execute(
            "UPDATE usage_tasks t SET started_at=a.t0, ended_at=a.t1, calls=a.n, input_tokens=a.i, "
            "cache_read_tokens=a.cr, cache_write_tokens=a.cw, output_tokens=a.o, max_call_input=a.mx, "
            "cost_list_nanousd=a.nano, cost_cli_microusd=a.cli, "
            "duration_ms=(extract(epoch FROM a.t1 - a.t0) * 1000)::bigint FROM ("
            "SELECT min(occurred_at) t0, max(occurred_at) t1, count(*) n, sum(input_tokens) i, "
            "sum(cache_read_tokens) cr, sum(COALESCE(cache_write_5m_tokens,0)+COALESCE(cache_write_1h_tokens,0)) "
            "FILTER (WHERE cache_write_5m_tokens IS NOT NULL OR cache_write_1h_tokens IS NOT NULL) cw, "
            "sum(output_tokens) o, max(context_tokens) mx, sum(cost_list_nanousd) nano, sum(cost_cli_microusd) cli "
            "FROM usage_calls WHERE task_id=%s) a WHERE t.id=%s", (tid, tid))

    @staticmethod
    def _refresh_daily(c, ws, project_id, rows) -> None:
        days = sorted({call.occurred_at.astimezone(timezone.utc).date() for call, _ in rows})
        if not days:
            return
        c.execute(
            "INSERT INTO usage_daily (workspace_id, project_id, day, model_id, source_kind, calls, input_tokens, "
            "cache_read_tokens, cache_write_tokens, output_tokens, cost_list_microusd, cost_cli_microusd, "
            "cli_covered_calls) SELECT workspace_id, project_id, (occurred_at AT TIME ZONE 'UTC')::date d, model_id, "
            "source_kind, count(*), COALESCE(sum(input_tokens),0), COALESCE(sum(cache_read_tokens),0), "
            "COALESCE(sum(COALESCE(cache_write_5m_tokens,0)+COALESCE(cache_write_1h_tokens,0)),0), "
            "COALESCE(sum(output_tokens),0), (COALESCE(sum(cost_list_nanousd),0) + 500) / 1000, "
            "sum(cost_cli_microusd), count(cost_cli_microusd) FROM usage_calls "
            "WHERE workspace_id=%s AND project_id IS NOT DISTINCT FROM %s AND (occurred_at AT TIME ZONE 'UTC')::date "
            "= ANY(%s) GROUP BY workspace_id, project_id, d, model_id, source_kind "
            "ON CONFLICT (workspace_id, COALESCE(project_id, '00000000-0000-0000-0000-000000000000'::uuid), day, "
            "model_id, source_kind) DO UPDATE SET calls=EXCLUDED.calls, input_tokens=EXCLUDED.input_tokens, "
            "cache_read_tokens=EXCLUDED.cache_read_tokens, cache_write_tokens=EXCLUDED.cache_write_tokens, "
            "output_tokens=EXCLUDED.output_tokens, cost_list_microusd=EXCLUDED.cost_list_microusd, "
            "cost_cli_microusd=EXCLUDED.cost_cli_microusd, cli_covered_calls=EXCLUDED.cli_covered_calls",
            (ws, project_id, days))

    # -- reads ----------------------------------------------------------------------------------------------
    def daily(self, ws, d_from: date, d_to: date, project):
        with self.pool.connection() as c:
            rows = c.execute(
                "SELECT day, model_id, source_kind, sum(calls)::bigint, sum(input_tokens)::bigint, "
                "sum(cache_read_tokens)::bigint, sum(cache_write_tokens)::bigint, sum(output_tokens)::bigint, "
                "sum(cost_list_microusd)::bigint, sum(cost_cli_microusd)::bigint, sum(cli_covered_calls)::bigint "
                "FROM usage_daily WHERE workspace_id=%s AND day BETWEEN %s AND %s AND (%s::uuid IS NULL OR "
                "project_id = %s::uuid) GROUP BY day, model_id, source_kind ORDER BY day, model_id, source_kind",
                (ws, d_from, d_to, project, project)).fetchall()
        return [DailyRow(*r) for r in rows]

    def calls(self, ws, t_from, t_to, project, min_input=None, model=None, before_id=None, limit=None):
        with self.pool.connection() as c:
            rows = c.execute(
                f"SELECT {CALL_COLS} FROM usage_calls WHERE workspace_id=%s AND occurred_at BETWEEN %s AND %s "
                "AND (%s::uuid IS NULL OR project_id=%s::uuid) AND (%s::bigint IS NULL OR context_tokens >= %s::bigint) "
                "AND (%s::text IS NULL OR model_id=%s::text) AND (%s::bigint IS NULL OR id < %s::bigint) "
                "ORDER BY id DESC LIMIT %s",
                (ws, t_from, t_to, project, project, min_input, min_input, model, model, before_id, before_id,
                 limit)).fetchall()
        return [_call(r) for r in rows]

    def sessions(self, ws, t_from, t_to, offset, limit):
        with self.pool.connection() as c:
            rows = c.execute(
                f"SELECT {SESSION_COLS} FROM usage_sessions WHERE workspace_id=%s AND started_at BETWEEN %s AND %s "
                "ORDER BY started_at DESC, id DESC OFFSET %s LIMIT %s", (ws, t_from, t_to, offset, limit)).fetchall()
        return [SessionRow(str(r[0]), str(r[1]), *r[2:]) for r in rows]

    def tasks(self, ws, t_from, t_to, project, offset=0, limit=None):
        with self.pool.connection() as c:
            rows = c.execute(
                f"SELECT {TASK_COLS} FROM usage_tasks WHERE workspace_id=%s AND started_at BETWEEN %s AND %s "
                "AND (%s::uuid IS NULL OR project_id=%s::uuid) ORDER BY started_at DESC, id DESC OFFSET %s LIMIT %s",
                (ws, t_from, t_to, project, project, offset, limit)).fetchall()
        return [TaskRow(str(r[0]), str(r[1]), *r[2:]) for r in rows]

    def task(self, ws, task_id):
        with self.pool.connection() as c:
            r = c.execute(f"SELECT {TASK_COLS} FROM usage_tasks WHERE workspace_id=%s AND id=%s",
                          (ws, task_id)).fetchone()
        return None if r is None else TaskRow(str(r[0]), str(r[1]), *r[2:])

    def update_task(self, ws, task_id, fields):
        fields = {k: v for k, v in fields.items() if k in TASK_FIELDS}
        if fields:
            sets = ", ".join(f"{k}=%s" for k in fields)  # keys come from the TASK_FIELDS allow-list
            with self.pool.connection() as c:
                c.execute(f"UPDATE usage_tasks SET {sets} WHERE workspace_id=%s AND id=%s",
                          (*fields.values(), ws, task_id))
        return self.task(ws, task_id)

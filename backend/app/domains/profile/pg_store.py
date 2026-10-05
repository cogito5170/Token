"""PostgreSQL Store over profiles / personal_stats / recommendations (docs/schema.sql). Pool is injected."""
from __future__ import annotations

import json

from .service import Stat

PROFILE_COLS = ("monthly_budget_microusd, task_budget_microusd, quality_floor_permille, preferred_models, "
                "preferred_providers, billing_mode, team_size, store_bodies")
PROFILE_KEYS = [c.strip() for c in PROFILE_COLS.split(",")]


class PgStore:
    def __init__(self, pool) -> None:
        self.pool = pool

    def get_profile(self, ws, user):
        with self.pool.connection() as c:
            r = c.execute(f"SELECT {PROFILE_COLS} FROM profiles WHERE user_id=%s AND workspace_id=%s",
                          (user, ws)).fetchone()
        if r is None:
            return None
        p = dict(zip(PROFILE_KEYS, r))
        p["preferred_models"], p["preferred_providers"] = list(p["preferred_models"]), list(p["preferred_providers"])
        return p

    def put_profile(self, ws, user, data):
        with self.pool.connection() as c:
            c.execute(f"INSERT INTO profiles (user_id, workspace_id, {PROFILE_COLS}) "
                      "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (user_id, workspace_id) DO UPDATE SET "
                      + ", ".join(f"{k}=EXCLUDED.{k}" for k in PROFILE_KEYS) + ", updated_at=now()",
                      (user, ws, *[data[k] for k in PROFILE_KEYS]))
        return self.get_profile(ws, user)

    def profile_users(self, ws):
        with self.pool.connection() as c:
            return [str(r[0]) for r in c.execute("SELECT user_id FROM profiles WHERE workspace_id=%s ORDER BY user_id",
                                                 (ws,)).fetchall()]

    def replace_stats(self, ws, user, stats):
        with self.pool.connection() as c:  # one transaction
            v = c.execute("SELECT COALESCE(MAX(version), 0) + 1 FROM personal_stats WHERE user_id=%s AND "
                          "workspace_id=%s", (user, ws)).fetchone()[0]
            c.execute("DELETE FROM personal_stats WHERE user_id=%s AND workspace_id=%s", (user, ws))
            for s in stats:
                c.execute("INSERT INTO personal_stats (user_id, workspace_id, task_kind, model_id, structure, "
                          "context_mode, tasks, correct, first_try_success, tokens_per_correct, "
                          "cost_list_per_correct_nanousd, cost_cli_per_correct_microusd, version) "
                          "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                          (user, ws, s.task_kind, s.model_id, s.structure, s.context_mode, s.tasks, s.correct,
                           s.first_try_success, s.tokens_per_correct, s.cost_list_per_correct_nanousd,
                           s.cost_cli_per_correct_microusd, v))
        return v

    def stats(self, ws, user):
        with self.pool.connection() as c:
            rows = c.execute("SELECT task_kind, model_id, structure, context_mode, tasks, correct, first_try_success, "
                             "tokens_per_correct, cost_list_per_correct_nanousd, cost_cli_per_correct_microusd, "
                             "version FROM personal_stats WHERE user_id=%s AND workspace_id=%s "
                             "ORDER BY task_kind, model_id, structure, context_mode", (user, ws)).fetchall()
        return [Stat(r[0], r[1], r[2], r[3], tasks=r[4], correct=r[5], first_try_success=r[6], tokens_per_correct=r[7],
                     cost_list_per_correct_nanousd=r[8], cost_cli_per_correct_microusd=r[9], version=r[10])
                for r in rows]

    def replace_recommendations(self, ws, user, recs):
        with self.pool.connection() as c:
            c.execute("DELETE FROM recommendations WHERE user_id=%s AND workspace_id=%s", (user, ws))
            for r in recs:
                c.execute("INSERT INTO recommendations (id, user_id, workspace_id, headline, current_config, "
                          "recommended_config, saving_permille, evidence_n, stats_version, proposal_id) "
                          "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                          (r["id"], user, ws, r["headline"], json.dumps(r["current_config"]),
                           json.dumps(r["recommended_config"]), r["saving_permille"], r["evidence_n"],
                           r["stats_version"], r.get("proposal_id")))

    def recommendations(self, ws, user):
        with self.pool.connection() as c:
            rows = c.execute("SELECT id, headline, current_config, recommended_config, saving_permille, evidence_n, "
                             "stats_version, proposal_id FROM recommendations WHERE user_id=%s AND workspace_id=%s "
                             "ORDER BY created_at, id", (user, ws)).fetchall()
        keys = ("id", "headline", "current_config", "recommended_config", "saving_permille", "evidence_n",
                "stats_version", "proposal_id")
        return [{**dict(zip(keys, r)), "id": str(r[0]), "proposal_id": None if r[7] is None else str(r[7])}
                for r in rows]

    def set_proposal(self, ws, user, rec_id, proposal_id):
        with self.pool.connection() as c:
            c.execute("UPDATE recommendations SET proposal_id=%s WHERE id=%s AND user_id=%s AND workspace_id=%s",
                      (proposal_id, rec_id, user, ws))

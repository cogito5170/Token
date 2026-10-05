"""Simulation stores: in-memory (tests) and PostgreSQL (`simulations` table, the only table this domain owns)."""
from __future__ import annotations

import json


class MemoryStore:
    def __init__(self) -> None:
        self.rows: dict[tuple[str, str], dict] = {}

    def save(self, ws: str, user: str, sim: dict) -> None:
        self.rows[(ws, sim["id"])] = {**sim, "_user": user}

    def get(self, ws: str, sim_id: str) -> dict | None:
        r = self.rows.get((ws, sim_id))
        return None if r is None else {k: v for k, v in r.items() if not k.startswith("_")}


class PgStore:
    def __init__(self, pool) -> None:
        self.pool = pool

    def save(self, ws: str, user: str, sim: dict) -> None:
        with self.pool.connection() as c:
            c.execute("INSERT INTO simulations (id, workspace_id, requested_by, assumptions, basis, result) "
                      "VALUES (%s, %s, %s, %s::jsonb, %s::jsonb, %s::jsonb)",
                      (sim["id"], ws, user, json.dumps(sim["assumptions"]), json.dumps(sim["basis"]),
                       json.dumps(sim["result"])))

    def get(self, ws: str, sim_id: str) -> dict | None:
        with self.pool.connection() as c:
            r = c.execute("SELECT id, assumptions, basis, result FROM simulations WHERE workspace_id = %s AND id = %s",
                          (ws, sim_id)).fetchone()
        if r is None:
            return None
        load = lambda v: json.loads(v) if isinstance(v, str) else v  # noqa: E731
        return {"id": str(r[0]), "assumptions": load(r[1]), "basis": load(r[2]), "result": load(r[3]),
                "provenance": "SIMULATED"}

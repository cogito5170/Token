"""PostgreSQL Store over sources / uploads (docs/schema.sql). Pool is injected."""
from __future__ import annotations

from .service import SourceRow, UploadRow

_U = "id, workspace_id, source_id, uploaded_by, filename, size_bytes, sha256, declared_format, storage_path, purge_after, purged_at"


class PgStore:
    def __init__(self, pool) -> None:
        self.pool = pool

    @staticmethod
    def _s(r):
        return SourceRow(str(r[0]), str(r[1]), r[2], r[3], None if r[4] is None else str(r[4]))

    @staticmethod
    def _u(r):
        return UploadRow(str(r[0]), str(r[1]), str(r[2]), str(r[3]), r[4], int(r[5]), r[6], r[7], r[8], r[9], r[10])

    def add_source(self, s):
        with self.pool.connection() as c:
            r = c.execute("INSERT INTO sources (workspace_id, project_id, kind, name) VALUES (%s,%s,%s,%s) "
                          "RETURNING id, workspace_id, kind, name, project_id",
                          (s.workspace_id, s.project_id, s.kind, s.name)).fetchone()
        return self._s(r)

    def sources(self, ws):
        with self.pool.connection() as c:
            rows = c.execute("SELECT id, workspace_id, kind, name, project_id FROM sources "
                             "WHERE workspace_id=%s ORDER BY created_at", (ws,)).fetchall()
        return [self._s(r) for r in rows]

    def source(self, ws, source_id):
        with self.pool.connection() as c:
            r = c.execute("SELECT id, workspace_id, kind, name, project_id FROM sources "
                          "WHERE workspace_id=%s AND id=%s", (ws, source_id)).fetchone()
        return None if r is None else self._s(r)

    def add_upload(self, u):
        with self.pool.connection() as c:
            r = c.execute(f"INSERT INTO uploads (id, workspace_id, source_id, uploaded_by, filename, size_bytes, sha256, "
                          f"declared_format, storage_path, purge_after) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) "
                          f"RETURNING {_U}",
                          (u.id, u.workspace_id, u.source_id, u.uploaded_by, u.filename, u.size_bytes, u.sha256,
                           u.declared_format, u.storage_path, u.purge_after)).fetchone()
        return self._u(r)

    def upload(self, upload_id):
        with self.pool.connection() as c:
            r = c.execute(f"SELECT {_U} FROM uploads WHERE id=%s", (upload_id,)).fetchone()
        return None if r is None else self._u(r)

    def set_purge_after(self, upload_id, when):
        with self.pool.connection() as c:
            c.execute("UPDATE uploads SET purge_after=%s WHERE id=%s AND purged_at IS NULL", (when, upload_id))

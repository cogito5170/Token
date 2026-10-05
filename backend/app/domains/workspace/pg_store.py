"""PostgreSQL Store over workspaces / workspace_members / projects (docs/schema.sql). Pool is injected."""
from __future__ import annotations

from .service import MemberRow, ProjectRow, WorkspaceRow


class PgStore:
    def __init__(self, pool) -> None:
        self.pool = pool

    @staticmethod
    def _w(r):
        return None if r is None else WorkspaceRow(str(r[0]), r[1], r[2], str(r[3]))

    def create_workspace(self, name, slug, created_by):
        with self.pool.connection() as c:
            return self._w(c.execute(
                "INSERT INTO workspaces (name, slug, created_by) VALUES (%s,%s,%s) ON CONFLICT DO NOTHING "
                "RETURNING id, name, slug, created_by", (name, slug, created_by)).fetchone())

    def workspace(self, ws):
        with self.pool.connection() as c:
            return self._w(c.execute("SELECT id, name, slug, created_by FROM workspaces WHERE id=%s",
                                     (ws,)).fetchone())

    def add_member(self, ws, user_id, role):
        with self.pool.connection() as c:
            return c.execute("INSERT INTO workspace_members (workspace_id, user_id, role) VALUES (%s,%s,%s) "
                             "ON CONFLICT DO NOTHING", (ws, user_id, role)).rowcount == 1

    def member(self, ws, user_id):
        with self.pool.connection() as c:
            r = c.execute("SELECT role FROM workspace_members WHERE workspace_id=%s AND user_id=%s",
                          (ws, user_id)).fetchone()
        return None if r is None else MemberRow(ws, user_id, str(r[0]))

    def members(self, ws):
        with self.pool.connection() as c:
            rows = c.execute("SELECT m.user_id, m.role, u.email FROM workspace_members m JOIN users u ON u.id=m.user_id "
                             "WHERE m.workspace_id=%s ORDER BY m.joined_at", (ws,)).fetchall()
        return [MemberRow(ws, str(r[0]), str(r[1]), r[2]) for r in rows]

    def workspaces_of(self, user_id):
        with self.pool.connection() as c:
            rows = c.execute("SELECT w.id, w.name, w.slug, w.created_by, m.role FROM workspaces w "
                             "JOIN workspace_members m ON m.workspace_id=w.id WHERE m.user_id=%s "
                             "ORDER BY w.created_at", (user_id,)).fetchall()
        return [(self._w(r[:4]), str(r[4])) for r in rows]

    def user_id_by_email(self, email):
        with self.pool.connection() as c:
            r = c.execute("SELECT id FROM users WHERE lower(email)=lower(%s) AND disabled_at IS NULL",
                          (email,)).fetchone()
        return None if r is None else str(r[0])

    def personal_workspace_exists(self, user_id):
        with self.pool.connection() as c:
            return c.execute("SELECT 1 FROM workspaces WHERE created_by=%s AND slug LIKE 'personal-%%'",
                             (user_id,)).fetchone() is not None

    def create_project(self, p):
        with self.pool.connection() as c:
            r = c.execute("INSERT INTO projects (id, workspace_id, name, repo_url, language, repo_size_loc) "
                          "VALUES (%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING RETURNING id",
                          (p.id, p.workspace_id, p.name, p.repo_url, p.language, p.repo_size_loc)).fetchone()
        return None if r is None else p

    def projects(self, ws):
        with self.pool.connection() as c:
            rows = c.execute("SELECT id, name, repo_url, language, repo_size_loc FROM projects "
                             "WHERE workspace_id=%s ORDER BY created_at", (ws,)).fetchall()
        return [ProjectRow(str(r[0]), ws, r[1], r[2], r[3], r[4]) for r in rows]

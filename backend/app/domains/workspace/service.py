"""Workspace use cases. Store and audit recorder are injected so the rules test without a DB.

Boundary rule (docs/security.md): a non-member sees 404 for any workspace (existence hidden); a member with too low a
role gets 403. Audit detail holds ids and roles only.
"""
from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from typing import Protocol

ROLES = ("viewer", "developer", "admin")  # ascending rank
RANK = {r: i for i, r in enumerate(ROLES)}


class WorkspaceError(Exception):
    """code: not_found | forbidden | invalid_request | already_member | project_exists | unknown_user"""

    def __init__(self, code: str, message: str, status: int):
        super().__init__(message)
        self.code, self.message, self.status = code, message, status


@dataclass
class WorkspaceRow:
    id: str
    name: str
    slug: str
    created_by: str


@dataclass
class MemberRow:
    workspace_id: str
    user_id: str
    role: str
    email: str | None = None


@dataclass
class ProjectRow:
    id: str
    workspace_id: str
    name: str
    repo_url: str | None = None
    language: str | None = None
    repo_size_loc: int | None = None


class Store(Protocol):
    def create_workspace(self, name: str, slug: str, created_by: str) -> WorkspaceRow | None: ...  # None if slug taken
    def workspace(self, ws: str) -> WorkspaceRow | None: ...
    def add_member(self, ws: str, user_id: str, role: str) -> bool: ...  # False if already a member
    def member(self, ws: str, user_id: str) -> MemberRow | None: ...
    def members(self, ws: str) -> list[MemberRow]: ...
    def workspaces_of(self, user_id: str) -> list[tuple[WorkspaceRow, str]]: ...
    def user_id_by_email(self, email: str) -> str | None: ...
    def personal_workspace_exists(self, user_id: str) -> bool: ...
    def create_project(self, p: ProjectRow) -> ProjectRow | None: ...  # None if name taken
    def projects(self, ws: str) -> list[ProjectRow]: ...


class MemoryStore:
    def __init__(self) -> None:
        self.ws: dict[str, WorkspaceRow] = {}
        self.mem: dict[tuple[str, str], MemberRow] = {}
        self.proj: dict[str, ProjectRow] = {}
        self.emails: dict[str, str] = {}  # lower(email) -> user_id (test hook for the identity lookup)

    def create_workspace(self, name, slug, created_by):
        if any(w.slug == slug for w in self.ws.values()):
            return None
        w = WorkspaceRow(str(uuid.uuid4()), name, slug, created_by)
        self.ws[w.id] = w
        return w

    def workspace(self, ws):
        return self.ws.get(ws)

    def add_member(self, ws, user_id, role):
        if (ws, user_id) in self.mem:
            return False
        self.mem[(ws, user_id)] = MemberRow(ws, user_id, role)
        return True

    def member(self, ws, user_id):
        return self.mem.get((ws, user_id))

    def members(self, ws):
        return [m for (w, _), m in self.mem.items() if w == ws]

    def workspaces_of(self, user_id):
        return [(self.ws[w], m.role) for (w, u), m in self.mem.items() if u == user_id]

    def user_id_by_email(self, email):
        return self.emails.get(email.lower())

    def personal_workspace_exists(self, user_id):
        return any(w.created_by == user_id and w.slug.startswith("personal-") for w in self.ws.values())

    def create_project(self, p):
        if any(x.workspace_id == p.workspace_id and x.name == p.name for x in self.proj.values()):
            return None
        self.proj[p.id] = p
        return p

    def projects(self, ws):
        return [p for p in self.proj.values() if p.workspace_id == ws]


def _noop_audit(action: str, actor: str | None, detail: dict) -> None:
    return None


def slugify(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return s or "workspace"


def _valid_uuid(x: str) -> bool:
    try:
        uuid.UUID(str(x))
        return True
    except ValueError:
        return False


class WorkspaceService:
    def __init__(self, store: Store, audit=_noop_audit) -> None:
        self.store, self.audit = store, audit

    def require_member(self, ws: str, user_id: str, min_role: str = "viewer") -> MemberRow:
        """404 for non-members (and unknown/malformed ws), 403 when the member's role is below min_role."""
        if min_role not in RANK:
            raise ValueError(f"bad role: {min_role}")
        m = self.store.member(ws, user_id) if _valid_uuid(ws) else None
        if m is None:
            raise WorkspaceError("not_found", "workspace not found", 404)
        if RANK[m.role] < RANK[min_role]:
            raise WorkspaceError("forbidden", f"requires role {min_role}", 403)
        return m

    def create_workspace(self, user_id: str, name: str) -> tuple[WorkspaceRow, str]:
        name = (name or "").strip()
        if not name or len(name) > 100:
            raise WorkspaceError("invalid_request", "name must be 1-100 characters", 422)
        base = slugify(name)
        for slug in [base] + [f"{base}-{uuid.uuid4().hex[:6]}" for _ in range(5)]:
            w = self.store.create_workspace(name, slug, user_id)
            if w:
                break
        else:
            raise WorkspaceError("invalid_request", "could not allocate a slug", 409)
        self.store.add_member(w.id, user_id, "admin")
        self.audit("workspace.created", user_id, {"workspace_id": w.id})
        return w, "admin"

    def ensure_personal(self, user_id: str) -> WorkspaceRow | None:
        """Handler of identity.user.created; idempotent."""
        if self.store.personal_workspace_exists(user_id):
            return None
        w = self.store.create_workspace("Personal", f"personal-{user_id[:8]}", user_id)
        if w is None:
            return None
        self.store.add_member(w.id, user_id, "admin")
        self.audit("workspace.created", user_id, {"workspace_id": w.id, "personal": True})
        return w

    def on_user_created(self, name: str, payload: dict) -> None:
        uid = payload.get("user_id")
        if uid:
            self.ensure_personal(str(uid))

    def list_workspaces(self, user_id: str):
        return self.store.workspaces_of(user_id)

    def get_workspace(self, ws: str, user_id: str) -> tuple[WorkspaceRow, str]:
        m = self.require_member(ws, user_id)
        return self.store.workspace(ws), m.role

    def member_ids(self, ws: str) -> list[str]:
        """User ids of every member (system-level lookup for other domains, e.g. notification fan-out); [] if unknown."""
        return [m.user_id for m in self.store.members(ws)] if _valid_uuid(ws) else []

    def members(self, ws: str, user_id: str) -> list[MemberRow]:
        self.require_member(ws, user_id)
        return self.store.members(ws)

    def add_member(self, ws: str, actor: str, email: str, role: str) -> MemberRow:
        self.require_member(ws, actor, "admin")
        if role not in RANK:
            raise WorkspaceError("invalid_request", "role must be admin, developer or viewer", 422)
        uid = self.store.user_id_by_email(email or "")
        if uid is None:
            raise WorkspaceError("unknown_user", "no such user", 404)
        if not self.store.add_member(ws, uid, role):
            raise WorkspaceError("already_member", "user is already a member", 409)
        self.audit("workspace.member_added", actor, {"workspace_id": ws, "user_id": uid, "role": role})
        return MemberRow(ws, uid, role, email)

    def create_project(self, ws: str, actor: str, name: str, repo_url=None, language=None, repo_size_loc=None):
        self.require_member(ws, actor, "developer")
        name = (name or "").strip()
        if not name or len(name) > 100:
            raise WorkspaceError("invalid_request", "name must be 1-100 characters", 422)
        if repo_size_loc is not None and repo_size_loc < 0:
            raise WorkspaceError("invalid_request", "repo_size_loc must be >= 0", 422)
        p = self.store.create_project(ProjectRow(str(uuid.uuid4()), ws, name, repo_url, language, repo_size_loc))
        if p is None:
            raise WorkspaceError("project_exists", "project name already used", 409)
        self.audit("workspace.project_created", actor, {"workspace_id": ws, "project_id": p.id})
        return p

    def projects(self, ws: str, user_id: str) -> list[ProjectRow]:
        self.require_member(ws, user_id)
        return self.store.projects(ws)

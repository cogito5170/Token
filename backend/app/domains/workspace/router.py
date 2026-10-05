"""FastAPI routes: /v1/workspaces, /{ws}, /{ws}/members, /{ws}/projects. Every {ws} route starts with require_member."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from .api import http_error, require_member
from .service import WorkspaceError
from .wiring import get_service, subscribe

from ._identity import current_user

router = APIRouter()
subscribe()


class WorkspaceCreate(BaseModel):
    name: str


class MemberAdd(BaseModel):
    email: str
    role: str


class ProjectCreate(BaseModel):
    name: str
    repo_url: str | None = None
    language: str | None = None
    repo_size_loc: int | None = None


def _w(w, role):
    return {"id": w.id, "name": w.name, "slug": w.slug, "role": role}


def _m(m):
    return {"user_id": m.user_id, "email": m.email, "role": m.role}


def _p(p):
    return {"id": p.id, "name": p.name, "language": p.language, "repo_size_loc": p.repo_size_loc}


@router.get("/v1/workspaces", tags=["workspace"])
def list_workspaces(user=Depends(current_user)):
    return [_w(w, r) for w, r in get_service().list_workspaces(user.id)]


@router.post("/v1/workspaces", status_code=201, tags=["workspace"])
def create_workspace(body: WorkspaceCreate, user=Depends(current_user)):
    try:
        return _w(*get_service().create_workspace(user.id, body.name))
    except WorkspaceError as e:
        raise http_error(e) from None


@router.get("/v1/workspaces/{ws}", tags=["workspace"])
def get_workspace(ws: str, user=Depends(current_user)):
    require_member(ws, user.id)
    return _w(*get_service().get_workspace(ws, user.id))


@router.get("/v1/workspaces/{ws}/members", tags=["workspace"])
def list_members(ws: str, user=Depends(current_user)):
    require_member(ws, user.id)
    return [_m(m) for m in get_service().members(ws, user.id)]


@router.post("/v1/workspaces/{ws}/members", status_code=201, tags=["workspace"])
def add_member(ws: str, body: MemberAdd, user=Depends(current_user)):
    require_member(ws, user.id, "admin")
    try:
        return _m(get_service().add_member(ws, user.id, body.email, body.role))
    except WorkspaceError as e:
        raise http_error(e) from None


@router.get("/v1/workspaces/{ws}/projects", tags=["workspace"])
def list_projects(ws: str, user=Depends(current_user)):
    require_member(ws, user.id)
    return [_p(p) for p in get_service().projects(ws, user.id)]


@router.post("/v1/workspaces/{ws}/projects", status_code=201, tags=["workspace"])
def create_project(ws: str, body: ProjectCreate, user=Depends(current_user)):
    require_member(ws, user.id, "developer")
    try:
        return _p(get_service().create_project(ws, user.id, body.name, body.repo_url, body.language,
                                               body.repo_size_loc))
    except WorkspaceError as e:
        raise http_error(e) from None

"""FastAPI routes: /v1/auth/{signup,login,refresh,logout}, /v1/me. Refresh token only travels in the gc_refresh cookie."""
from __future__ import annotations

from fastapi import APIRouter, Cookie, Depends, Header, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.core import events
from app.core.config import load_settings

from .passwords import Argon2Hasher
from .service import AuthError, IdentityService
from .tokens import REFRESH_TTL

router = APIRouter()
COOKIE = "gc_refresh"
_service: IdentityService | None = None
_audit = None


def set_audit_recorder(fn) -> None:
    """Wire audit.api.record here once GC15 lands; until then audit is a no-op."""
    global _audit, _service
    _audit, _service = fn, None


def get_service() -> IdentityService:
    global _service
    if _service is None:
        from app.core.db import get_pool

        from .pg_store import PgStore

        kw = {"audit": _audit} if _audit else {}
        _service = IdentityService(PgStore(get_pool()), Argon2Hasher(), load_settings().jwt_secret or "",
                                   publish=events.bus.publish, **kw)
    return _service


class SignupRequest(BaseModel):
    email: str
    password: str
    display_name: str = ""


class LoginRequest(BaseModel):
    email: str
    password: str


def _err(e: AuthError) -> JSONResponse:
    return JSONResponse({"code": e.code, "message": e.message}, status_code=e.status)


def _pair(t, status: int = 200) -> JSONResponse:
    r = JSONResponse({"access_token": t.access_token, "expires_in": t.expires_in}, status_code=status)
    r.set_cookie(COOKIE, t.refresh_token, max_age=REFRESH_TTL, httponly=True, secure=True,
                 samesite="strict", path="/v1/auth")
    return r


@router.post("/v1/auth/signup", status_code=201, tags=["identity"])
def signup(body: SignupRequest, svc: IdentityService = Depends(get_service)):
    try:
        return _pair(svc.signup(body.email, body.password, body.display_name), status=201)
    except AuthError as e:
        return _err(e)


@router.post("/v1/auth/login", tags=["identity"])
def login(body: LoginRequest, request: Request, svc: IdentityService = Depends(get_service)):
    ip = request.client.host if request.client else ""
    try:
        return _pair(svc.login(body.email, body.password, ip))
    except AuthError as e:
        return _err(e)


@router.post("/v1/auth/refresh", tags=["identity"])
def refresh(gc_refresh: str | None = Cookie(default=None), svc: IdentityService = Depends(get_service)):
    try:
        return _pair(svc.refresh(gc_refresh))
    except AuthError as e:
        return _err(e)


@router.post("/v1/auth/logout", status_code=204, tags=["identity"])
def logout(gc_refresh: str | None = Cookie(default=None), svc: IdentityService = Depends(get_service)):
    svc.logout(gc_refresh)
    r = Response(status_code=204)
    r.delete_cookie(COOKIE, path="/v1/auth")
    return r


def _unauth() -> HTTPException:
    return HTTPException(401, detail={"code": "invalid_token", "message": "invalid or expired token"},
                         headers={"WWW-Authenticate": "Bearer"})


def current_user(authorization: str | None = Header(default=None), svc: IdentityService = Depends(get_service)):
    """identity.api.current_user: the dependency other domains use to require a logged-in user."""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise _unauth()
    try:
        return svc.authenticate(authorization[7:].strip())
    except AuthError:
        raise _unauth() from None


@router.get("/v1/me", tags=["identity"])
def me(user=Depends(current_user)):
    return {"id": user.id, "email": user.email, "display_name": user.display_name}

"""FastAPI routes: /v1/workspaces/{ws}/monitor/sources[/{source}/(snapshot|events|recordings[/{recording}])].

App-side live monitor over the read-only .ga reader (CMD-RN1: gadir, snapshot, sidecar.Monitor). Read = member;
register = admin (audited). Nothing here writes inside a registered .ga directory, and there is no control endpoint:
every route reads. A recording is the event log of the running reader (kept in memory, outside the .ga dir).
The x-later /runs paths are not served.
"""
from __future__ import annotations

import json
import os
import re
import threading
import time
import uuid

from fastapi import APIRouter, Body, Depends, Header, HTTPException
from fastapi.responses import Response, StreamingResponse

from app.domains.identity.api import current_user
from app.domains.workspace.api import require_member

from .gadir import READER_VERSION
from .sidecar import HEARTBEAT_S, Monitor

router = APIRouter()
_BASE = "/v1/workspaces/{ws}/monitor/sources"


def _err(status: int, code: str, message: str) -> HTTPException:
    return HTTPException(status, detail={"code": code, "message": message})


def _uuid(s: str) -> str | None:
    try:
        return str(uuid.UUID(s))
    except ValueError:
        return None


# ------------------------------------------------------------------------------------------------ source store
class MemorySources:
    def __init__(self) -> None:
        self.rows: dict[str, dict] = {}

    def list(self, ws):
        return [r for r in self.rows.values() if r["workspace_id"] == ws]

    def get(self, ws, sid):
        r = self.rows.get(sid)
        return r if r and r["workspace_id"] == ws else None

    def add(self, ws, label, path, user_id):
        if any(r["path"] == path for r in self.list(ws)):
            raise _err(409, "conflict", "this directory is already registered")
        r = {"id": str(uuid.uuid4()), "workspace_id": ws, "label": label, "path": path}
        self.rows[r["id"]] = r
        return r


class PgSources:
    """ga_dirs (docs/schema.sql). The path is only ever opened for reading."""

    def __init__(self, pool) -> None:
        self.pool = pool

    @staticmethod
    def _r(x):
        return {"id": str(x[0]), "workspace_id": str(x[1]), "label": x[2], "path": x[3]}

    def list(self, ws):
        with self.pool.connection() as c:
            return [self._r(x) for x in c.execute("SELECT id, workspace_id, label, path FROM ga_dirs "
                                                  "WHERE workspace_id=%s ORDER BY created_at, id", (ws,)).fetchall()]

    def get(self, ws, sid):
        with self.pool.connection() as c:
            x = c.execute("SELECT id, workspace_id, label, path FROM ga_dirs WHERE workspace_id=%s AND id=%s",
                          (ws, sid)).fetchone()
        return self._r(x) if x else None

    def add(self, ws, label, path, user_id):
        import psycopg
        try:
            with self.pool.connection() as c:
                x = c.execute("INSERT INTO ga_dirs (workspace_id, label, path, created_by) VALUES (%s,%s,%s,%s) "
                              "RETURNING id, workspace_id, label, path", (ws, label, path, user_id)).fetchone()
        except psycopg.errors.UniqueViolation:
            raise _err(409, "conflict", "this directory is already registered") from None
        return self._r(x)


_sources = None


def set_sources(store) -> None:
    global _sources
    _sources = store


def get_sources():
    global _sources
    if _sources is None:
        from app.core.db import get_pool
        _sources = PgSources(get_pool())
    return _sources


def _record(*a, **k):
    from app.domains.audit.api import record
    return record(*a, **k)


# ------------------------------------------------------------------------------------------------ live readers
_monitors: dict[str, Monitor] = {}
_lock = threading.Lock()


def _monitor(src: dict) -> Monitor:
    """One polling reader per registered source (per path). Never given a record dir: nothing is written to disk."""
    key = src["id"] + "\0" + src["path"]
    with _lock:
        mon = _monitors.get(key)
        if mon is None:
            mon = Monitor(src["path"], int(os.environ.get("GC_MONITOR_POLL_MS", "500")))
            threading.Thread(target=mon.run, daemon=True).start()
            _monitors[key] = mon
        return mon


def stop_monitors() -> None:
    with _lock:
        for m in _monitors.values():
            m.stop = True
        _monitors.clear()


def _source(ws: str, source: str) -> dict:
    sid = _uuid(source)
    src = get_sources().get(ws, sid) if sid else None
    if src is None:
        raise _err(404, "not_found", "source not found")
    return src


def _view(src: dict) -> dict:
    return {"id": src["id"], "label": src["label"], "path": src["path"], "reachable": os.path.isdir(src["path"])}


def _line(e: dict) -> str:
    return json.dumps(e, separators=(",", ":"), sort_keys=True)


def sse_frames(mon: Monitor, after: int, heartbeat_s: float = HEARTBEAT_S, done=lambda: False):
    """SSE bytes for every event with seq > after, then new ones as they arrive; `: heartbeat` comments when idle."""
    seq, last_beat = after, time.monotonic()
    while not mon.stop and not done():
        evs = mon.events_after(seq)
        for e in evs:
            yield f"id: {e['seq']}\nevent: {e['kind']}\ndata: {json.dumps(e, separators=(',', ':'))}\n\n".encode()
            seq = e["seq"]
        if evs:
            last_beat = time.monotonic()
        elif time.monotonic() - last_beat >= heartbeat_s:
            yield b": heartbeat\n\n"
            last_beat = time.monotonic()
        with mon.cond:
            mon.cond.wait(timeout=min(0.5, heartbeat_s))


# ------------------------------------------------------------------------------------------------ routes
@router.get(_BASE, tags=["run"])
def list_monitor_sources(ws: str, user=Depends(current_user)):
    require_member(ws, user.id)
    return [_view(s) for s in get_sources().list(ws)]


@router.post(_BASE, tags=["run"], status_code=201)
def register_monitor_source(ws: str, body: dict = Body(...), user=Depends(current_user)):
    require_member(ws, user.id, "admin")
    label, path = body.get("label"), body.get("path")
    if not isinstance(label, str) or not label.strip() or len(label) > 200:
        raise _err(422, "invalid_request", "label must be 1-200 characters")
    if not isinstance(path, str) or not os.path.isabs(path) or "\0" in path:
        raise _err(422, "invalid_request", "path must be an absolute path")
    path = os.path.realpath(path)
    if not os.path.isdir(path):
        raise _err(422, "invalid_request", "path is not a directory")
    src = get_sources().add(ws, label.strip(), path, user.id)
    _record("monitor.source_registered", user.id, {"workspace_id": ws, "source_id": src["id"]}, workspace_id=ws,
            target_kind="ga_dir", target_id=src["id"])
    return _view(src)


@router.get(_BASE + "/{source}/snapshot", tags=["run"])
def monitor_snapshot(ws: str, source: str, user=Depends(current_user)):
    require_member(ws, user.id)
    mon = _monitor(_source(ws, source))
    with mon.cond:
        return mon.reader.full_snapshot()


@router.get(_BASE + "/{source}/events", tags=["run"])
def stream_monitor_events(ws: str, source: str, user=Depends(current_user),
                          last_event_id: str | None = Header(None, alias="Last-Event-ID")):
    require_member(ws, user.id)
    mon = _monitor(_source(ws, source))
    if last_event_id is not None and not re.fullmatch(r"[0-9]{1,18}", last_event_id.strip()):
        raise _err(422, "invalid_request", "Last-Event-ID must be a non-negative integer")
    after = int(last_event_id) if last_event_id is not None else 0
    return StreamingResponse(sse_frames(mon, after), media_type="text/event-stream",
                             headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"})


@router.get(_BASE + "/{source}/recordings", tags=["run"])
def list_monitor_recordings(ws: str, source: str, user=Depends(current_user)):
    require_member(ws, user.id)
    mon = _monitor(_source(ws, source))
    with mon.cond:
        n = len(mon.reader.events)
    return [{"id": mon.recording_id, "started_at": mon.started_at, "ended_at": None, "events": n,
             "reader_version": READER_VERSION}]


@router.get(_BASE + "/{source}/recordings/{recording}", tags=["run"])
def get_monitor_recording(ws: str, source: str, recording: str, user=Depends(current_user)):
    require_member(ws, user.id)
    mon = _monitor(_source(ws, source))
    if recording != mon.recording_id:
        raise _err(404, "not_found", "recording not found")
    return Response("".join(_line(e) + "\n" for e in mon.events_after(0)), media_type="application/x-ndjson")

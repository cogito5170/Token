"""FastAPI routes: /v1/workspaces/{ws}/ingest-jobs*. Every route starts with require_member."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import StreamingResponse

from app.domains.workspace.api import require_member

from ._identity import current_user
from .service import IngestError, JobRow
from .wiring import get_service

router = APIRouter()


def _err(e: IngestError) -> HTTPException:
    return HTTPException(e.status, detail={"code": e.code, "message": e.code})


def job_json(j: JobRow) -> dict:
    iso = lambda t: t.isoformat() if t else None  # noqa: E731
    return {"id": j.id, "upload_id": j.upload_id, "state": j.state, "source_kind": j.source_kind, "parser": j.parser,
            "inserted": j.inserted, "duplicates": j.duplicates, "rejected": j.rejected,
            "last_error_code": j.last_error_code, "created_at": iso(j.created_at), "finished_at": iso(j.finished_at)}


@router.get("/v1/workspaces/{ws}/ingest-jobs", tags=["ingestion"])
def list_ingest_jobs(ws: str, user=Depends(current_user)):
    require_member(ws, user.id)
    return [job_json(j) for j in get_service().list_jobs(ws)]


@router.get("/v1/workspaces/{ws}/ingest-jobs/{job}", tags=["ingestion"])
def get_ingest_job(ws: str, job: str, user=Depends(current_user)):
    require_member(ws, user.id)
    try:
        return job_json(get_service().get_job(ws, job))
    except IngestError as e:
        raise _err(e) from None


@router.get("/v1/workspaces/{ws}/ingest-jobs/{job}/events", tags=["ingestion"])
def stream_ingest_job_events(ws: str, job: str, last_event_id: str | None = Header(None, alias="Last-Event-ID"),
                             user=Depends(current_user)):
    require_member(ws, user.id)
    try:
        last = int(last_event_id) if last_event_id and last_event_id.strip().isdigit() else 0
        gen = get_service().stream(ws, job, last)
        first = next(gen, None)  # raises not_found before the 200 starts
    except IngestError as e:
        raise _err(e) from None

    def frames():
        if first is not None:
            yield first
            yield from gen

    return StreamingResponse(frames(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

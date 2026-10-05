"""Source use cases: sources and uploads. Store, object store, event publisher and enqueuer are injected.

Upload bytes stream to the object store in chunks while sha256 and size are computed; past `max_bytes` the partial
object is removed and the call fails with 413. The event carries ids only (never the filename or content).
"""
from __future__ import annotations

import hashlib
import os
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import BinaryIO, Callable, Protocol

KINDS = ("upload",)  # creatable via the API; the other kinds in the schema are connectors (later)
FORMATS = ("claude_code", "ga_l0", "anthropic_export", "openai_export", "otel")
CHUNK = 1024 * 1024
PURGE_DAYS = 7  # docs/security.md


class SourceError(Exception):
    """code: invalid_request | not_found | payload_too_large"""

    def __init__(self, code: str, message: str, status: int):
        super().__init__(message)
        self.code, self.message, self.status = code, message, status


@dataclass
class SourceRow:
    id: str
    workspace_id: str
    kind: str
    name: str
    project_id: str | None = None


@dataclass
class UploadRow:
    id: str
    workspace_id: str
    source_id: str
    uploaded_by: str
    filename: str
    size_bytes: int
    sha256: str
    declared_format: str | None
    storage_path: str
    purge_after: datetime | None = None
    purged_at: datetime | None = None
    job_id: str | None = None


class Store(Protocol):
    def add_source(self, s: SourceRow) -> SourceRow: ...
    def sources(self, ws: str) -> list[SourceRow]: ...
    def source(self, ws: str, source_id: str) -> SourceRow | None: ...
    def add_upload(self, u: UploadRow) -> UploadRow: ...
    def upload(self, upload_id: str) -> UploadRow | None: ...
    def set_purge_after(self, upload_id: str, when: datetime) -> None: ...


class MemoryStore:
    def __init__(self) -> None:
        self.src: dict[str, SourceRow] = {}
        self.up: dict[str, UploadRow] = {}

    def add_source(self, s):
        self.src[s.id] = s
        return s

    def sources(self, ws):
        return [s for s in self.src.values() if s.workspace_id == ws]

    def source(self, ws, source_id):
        s = self.src.get(source_id)
        return s if s and s.workspace_id == ws else None

    def add_upload(self, u):
        self.up[u.id] = u
        return u

    def upload(self, upload_id):
        return self.up.get(upload_id)

    def set_purge_after(self, upload_id, when):
        if upload_id in self.up:
            self.up[upload_id].purge_after = when


class FileObjectStore:
    """Local directory object store. Keys are `<ws>/<upload_id>`; never exposed as URLs."""

    def __init__(self, root: str) -> None:
        self.root = os.path.abspath(root)

    def _path(self, key: str) -> str:
        p = os.path.abspath(os.path.join(self.root, key))
        if not p.startswith(self.root + os.sep):
            raise ValueError("bad key")
        return p

    def put(self, key: str, chunks) -> None:
        p = self._path(key)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        tmp = p + ".part"
        try:
            with open(tmp, "wb") as f:
                for c in chunks:
                    f.write(c)
            os.replace(tmp, p)
        finally:
            if os.path.exists(tmp):
                os.remove(tmp)

    def open(self, key: str) -> BinaryIO:
        return open(self._path(key), "rb")

    def delete(self, key: str) -> None:
        try:
            os.remove(self._path(key))
        except FileNotFoundError:
            pass


def _valid_uuid(x) -> bool:
    try:
        uuid.UUID(str(x))
        return True
    except ValueError:
        return False


def clean_filename(name: str | None) -> str:
    n = os.path.basename((name or "").replace("\\", "/")).strip()
    return n[:255] or "upload"


class _TooLarge(Exception):
    pass


class SourceService:
    def __init__(self, store: Store, objects, max_bytes: int, publish: Callable[[str, dict], object] = lambda n, p: 0,
                 enqueue: Callable[[str], str | None] | None = None, now=lambda: datetime.now(timezone.utc)) -> None:
        self.store, self.objects, self.max_bytes = store, objects, max_bytes
        self.publish, self.enqueue, self.now = publish, enqueue, now

    def create_source(self, ws: str, kind: str, name: str, project_id: str | None = None) -> SourceRow:
        name = (name or "").strip()
        if kind not in KINDS or not name or len(name) > 200:
            raise SourceError("invalid_request", "kind must be 'upload' and name 1-200 chars", 422)
        if project_id is not None and not _valid_uuid(project_id):
            raise SourceError("invalid_request", "bad project_id", 422)
        return self.store.add_source(SourceRow(str(uuid.uuid4()), ws, kind, name, project_id))

    def sources(self, ws: str) -> list[SourceRow]:
        return self.store.sources(ws)

    def get_source(self, ws: str, source_id: str) -> SourceRow | None:
        return self.store.source(ws, source_id) if _valid_uuid(source_id) else None

    def create_upload(self, ws: str, user_id: str, source_id: str, filename: str, file: BinaryIO,
                      declared_format: str | None = None, declared_size: int | None = None) -> UploadRow:
        if self.get_source(ws, source_id) is None:
            raise SourceError("not_found", "source not found", 404)
        if declared_format is not None and declared_format not in FORMATS:
            raise SourceError("invalid_request", "unknown declared_format", 422)
        too_big = SourceError("payload_too_large", f"file exceeds {self.max_bytes} bytes", 413)
        if declared_size is not None and declared_size > self.max_bytes:
            raise too_big
        uid = str(uuid.uuid4())
        key = f"{ws}/{uid}"
        h, size = hashlib.sha256(), 0

        def chunks():
            nonlocal size
            while True:
                c = file.read(CHUNK)
                if not c:
                    return
                size += len(c)
                if size > self.max_bytes:
                    raise _TooLarge
                h.update(c)
                yield c

        try:
            self.objects.put(key, chunks())
        except _TooLarge:
            self.objects.delete(key)
            raise too_big from None
        u = self.store.add_upload(UploadRow(
            uid, ws, source_id, user_id, clean_filename(filename), size, h.hexdigest(), declared_format, key,
            purge_after=self.now() + timedelta(days=PURGE_DAYS)))
        self.publish("source.upload.stored", {"workspace_id": ws, "source_id": source_id, "upload_id": uid})
        if self.enqueue is not None:
            u.job_id = self.enqueue(uid)
        return u

    def open_upload(self, upload_id: str) -> BinaryIO:
        u = self.store.upload(upload_id) if _valid_uuid(upload_id) else None
        if u is None or u.purged_at is not None:
            raise SourceError("not_found", "upload not found", 404)
        return self.objects.open(u.storage_path)

    def on_job_finished(self, name: str, payload: dict) -> None:
        """ingestion.job.finished: (re)start the purge clock for the original file."""
        uid = payload.get("upload_id")
        if uid and _valid_uuid(uid):
            self.store.set_purge_after(uid, self.now() + timedelta(days=PURGE_DAYS))

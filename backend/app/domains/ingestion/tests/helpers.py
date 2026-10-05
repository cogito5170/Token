import io
from datetime import datetime, timezone

from app.domains.ingestion import registry
from app.domains.ingestion.service import IngestService, MemoryStore
from types import SimpleNamespace

from app.domains.usage.api import CallIn

WS = "00000000-0000-4000-8000-000000000001"
SRC = "00000000-0000-4000-8000-0000000000aa"
T0 = datetime(2026, 3, 1, 12, 0, tzinfo=timezone.utc)


class FakeAdapter:
    """One call per line `model,in,out`; a line starting with `!` is rejected; `BOOM` raises with a secret-looking message."""
    kind, parser = "claude_code", "fake@0"

    def detect(self, filename, head):
        return head.startswith(b"FAKE")

    def parse(self, f):
        for n, line in enumerate(f.read().decode().splitlines()[1:], start=2):
            if line.startswith("BOOM"):
                raise RuntimeError("leaked prompt text sk-ant-FAKEFAKE")
            if line.startswith("!"):
                yield registry.ParsedReject(n, "bad_line")
                continue
            m, i, o = line.split(",")
            yield registry.ParsedCall(n, CallIn(m, "anthropic", "claude_code", T0, f"k-{m}-{n}-{i}",
                                                input_tokens=int(i), output_tokens=int(o)))


def fake_get_upload(files, ws=WS, src=SRC):
    """Stands in for source.api.get_upload (raises like it does for a missing upload)."""
    def get_upload(uid):
        if uid not in files:
            raise LookupError(uid)
        return {"workspace_id": ws, "source_id": src, "declared_format": None, "filename": "f.jsonl"}
    return get_upload


def fake_loader():
    """Stands in for usage.api.load_calls: dedupe on dedupe_key, unknown models rejected (no content)."""
    seen = set()

    def load_calls(ws, project_id, source_id, job_id, calls, sessions=None, tasks=None):
        ins = dup = 0
        rej = []
        for i, c in enumerate(calls):
            if c.model_id.startswith("no-such"):
                rej.append({"index": i, "code": "unknown_model"})
            elif (ws, c.dedupe_key) in seen:
                dup += 1
            else:
                seen.add((ws, c.dedupe_key))
                ins += 1
        return SimpleNamespace(inserted=ins, duplicates=dup, rejected=rej)
    return load_calls


def make(files: dict[str, bytes], max_attempts=3):
    """-> (service, store, None); every file is an upload with its own queued job."""
    store = MemoryStore()
    registry.register(FakeAdapter())
    svc = IngestService(store, lambda uid: io.BytesIO(files[uid]), fake_get_upload(files), fake_loader(),
                        lambda ws, sid: None, max_attempts=max_attempts)
    return svc, store, None

import io
from datetime import datetime, timezone

from app.domains.ingestion import registry
from app.domains.ingestion.service import IngestService, MemoryStore
from app.domains.usage.service import CallIn, MemoryStore as UsageMemory, UsageService

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


def make(files: dict[str, bytes], max_attempts=3):
    """-> (service, store, usage_service); every file is an upload with its own queued job."""
    store, usage = MemoryStore(), UsageService(UsageMemory())
    registry.register(FakeAdapter())
    svc = IngestService(store, lambda uid: io.BytesIO(files[uid]), usage.load_calls, lambda ws, sid: None,
                        max_attempts=max_attempts)
    for uid in files:
        store.register_upload(uid, WS, SRC)
    return svc, store, usage

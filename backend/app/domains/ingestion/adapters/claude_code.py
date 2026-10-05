"""Claude Code transcripts via telemetry.collect.from_cc_jsonl (pinned l0-telemetry). One llm.response = one call."""
from __future__ import annotations

import hashlib
import os
import tempfile
from typing import BinaryIO, Iterable

from app.domains.ingestion import registry
from app.domains.usage.api import CallIn

from .common import content_digest, dedupe, drop_bodies, get, to_dt, usage_ints


class ClaudeCodeAdapter:
    kind, parser = "claude_code", "telemetry.collect.from_cc_jsonl@f6c7ae2"

    def __init__(self, store_bodies: bool = False, hasher=None):
        self.store_bodies, self.hasher = store_bodies, hasher

    def detect(self, filename: str, head: bytes) -> bool:
        return filename.endswith(".jsonl") and b'"sessionId"' in head and b'"type"' in head

    def parse(self, f: BinaryIO) -> Iterable[object]:
        from telemetry.collect import from_cc_jsonl  # pinned parser; ImportError surfaces as a job error code
        raw = f.read()
        run_id = hashlib.sha256(raw).hexdigest()[:16]
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "cc.jsonl")
            with open(path, "wb") as out:
                out.write(raw)
            events = list(from_cc_jsonl(path, run_id, self.hasher))
        for n, ev in enumerate(events, start=1):
            if get(ev, "type") != "llm.response":
                continue
            raw_data = get(ev, "data") or {}
            ph, ch = content_digest(raw_data)  # hash first, then the bodies are dropped
            data = drop_bodies(raw_data, self.store_bodies)
            u = usage_ints(data)
            at, basis = to_dt(get(ev, "at"))
            idx = data.get("call_index")
            yield registry.ParsedCall(n, CallIn(
                model_id=data.get("model") or "unknown", provider="anthropic", source_kind=self.kind,
                occurred_at=at, time_basis=basis, call_index=idx, role="main",
                dedupe_key=dedupe(self.kind, run_id, data.get("response_id") or idx or n),
                tool_calls=data.get("tool_calls"), latency_ms=data.get("latency_ms"),
                prompt_prefix_hash=ph or data.get("prompt_prefix_hash") or None,
                content_hashes=ch or data.get("content_hashes") or None,
                session=run_id, **u))

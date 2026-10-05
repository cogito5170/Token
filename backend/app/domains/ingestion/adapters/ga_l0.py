"""ga L0 ledgers via telemetry.ledger.read_lenient (pinned). llm.response wins; else run.end = one turn call."""
from __future__ import annotations

import os
import tempfile
from typing import BinaryIO, Iterable

from app.domains.ingestion import registry
from app.domains.usage.api import CallIn

from .common import content_digest, dedupe, drop_bodies, get, to_dt, usage_ints


def _micro(usd) -> int | None:
    return round(usd * 1_000_000) if isinstance(usd, (int, float)) and not isinstance(usd, bool) else None


class GaL0Adapter:
    kind, parser = "ga_l0", "telemetry.ledger.read_lenient@f6c7ae2"

    def __init__(self, store_bodies: bool = False):
        self.store_bodies = store_bodies

    def detect(self, filename: str, head: bytes) -> bool:
        return filename.endswith(".jsonl") and b"l0-telemetry" in head

    def parse(self, f: BinaryIO) -> Iterable[object]:
        from telemetry.ledger import read_lenient
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "l0.jsonl")
            with open(path, "wb") as out:
                out.write(f.read())
            res = read_lenient(path)
        events, bad = (res if isinstance(res, tuple) else (res, []))
        events = list(events)
        for b in bad:  # bad lines: line number + code only, never the raw line
            yield registry.ParsedReject(int(get(b, "line_no", 0) or 0), "bad_line")
        has_resp = any(get(e, "type") == "llm.response" for e in events)
        for n, ev in enumerate(events, start=1):
            t = get(ev, "type")
            if t not in ("llm.response", "run.end") or (t == "run.end" and has_resp):
                continue
            raw_data = get(ev, "data") or {}
            ph, ch = content_digest(raw_data) if t == "llm.response" else (None, None)
            data = drop_bodies(raw_data, self.store_bodies)
            at, basis = to_dt(get(ev, "at"))
            if t == "llm.response":
                u = usage_ints(data)
            else:
                u = usage_ints({"input_tokens": data.get("reported_input_tokens"),
                                "output_tokens": data.get("reported_output_tokens"),
                                "cache_read_tokens": data.get("reported_cache_read_tokens")})
            run = get(ev, "run_id") or ""
            yield registry.ParsedCall(n, CallIn(
                model_id=data.get("model") or "unknown", provider=data.get("provider") or "anthropic",
                source_kind=self.kind, occurred_at=at, time_basis=basis, call_index=data.get("call_index"),
                role="turn" if t == "run.end" else "main", dedupe_key=dedupe(self.kind, run, t, get(ev, "seq", n)),
                cost_cli_microusd=_micro(data.get("cost_usd")), prompt_prefix_hash=ph, content_hashes=ch, tool_calls=data.get("api_calls"),
                session=run or None, **u))

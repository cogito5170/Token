"""Shared adapter helpers. Parsers come from the pinned packages (l0-telemetry, rlo-sdk), imported lazily so the
module loads without them; adapters never parse JSONL or transcripts themselves."""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone

# Fields of an L0 usage dict -> CallIn token columns.
USAGE_FIELDS = ("input_tokens", "cache_read_tokens", "cache_write_5m_tokens", "cache_write_1h_tokens",
                "output_tokens", "thinking_tokens")
BODY_KEYS = frozenset({"text", "content", "prompt", "completion", "message", "messages", "body", "output", "input_text"})


def get(obj, key, default=None):
    """Read a field from a dict or an attribute object (parsers may return either)."""
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def usage_ints(u: dict | None) -> dict:
    """Integer token columns from an l0 usage dict; absent / None stays None (reported_null)."""
    out = {}
    for f in USAGE_FIELDS:
        v = (u or {}).get(f)
        out[f] = int(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None
    return out


def drop_bodies(data, store_bodies: bool = False):
    """Remove prompt / completion bodies from a parser event payload unless store_bodies; kept bodies are scrubbed."""
    from app.domains.ingestion.scrub import scrub_value
    if not isinstance(data, dict):
        return data
    if store_bodies:
        return scrub_value(data)
    return {k: drop_bodies(v) if isinstance(v, dict) else v for k, v in data.items() if k not in BODY_KEYS}


def to_dt(v) -> tuple[datetime, str]:
    """(timestamp, time_basis); missing time -> now with basis 'ingested'."""
    if isinstance(v, datetime):
        return (v if v.tzinfo else v.replace(tzinfo=timezone.utc)), "reported"
    if isinstance(v, (int, float)) and not isinstance(v, bool) and v > 0:
        return datetime.fromtimestamp(v / 1000 if v > 1e11 else v, tz=timezone.utc), "reported"
    if isinstance(v, str) and v:
        try:
            d = datetime.fromisoformat(v.replace("Z", "+00:00"))
            return (d if d.tzinfo else d.replace(tzinfo=timezone.utc)), "reported"
        except ValueError:
            pass
    return datetime.now(timezone.utc), "ingested"


def dedupe(*parts) -> str:
    return hashlib.sha256("\x1f".join(str(p) for p in parts).encode()).hexdigest()

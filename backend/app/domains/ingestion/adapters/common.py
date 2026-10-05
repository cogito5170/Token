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


def l0_tokens(fields: dict | None) -> dict:
    """CallIn token columns from the fields dict of telemetry.usage.l0_usage (l0 names). Missing/None stays None.
    A cache-write total without the 5m/1h split goes to the 5m column."""
    f = fields or {}
    w5, w1 = f.get("cache_creation_5m_input_tokens"), f.get("cache_creation_1h_input_tokens")
    if w5 is None and w1 is None:
        w5 = f.get("cache_creation_input_tokens")
    return usage_ints({"input_tokens": f.get("input_tokens"), "cache_read_tokens": f.get("cache_read_input_tokens"),
                       "cache_write_5m_tokens": w5, "cache_write_1h_tokens": w1,
                       "output_tokens": f.get("output_tokens"), "thinking_tokens": f.get("thinking_tokens")})


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


PREFIX_BYTES = 4096


def _flatten(v) -> list[str]:
    """Text blocks of a body value (str | list | dict with a body key); non-text values contribute nothing."""
    if isinstance(v, str):
        return [v] if v else []
    if isinstance(v, (list, tuple)):
        return [t for x in v for t in _flatten(x)]
    if isinstance(v, dict):
        for k in ("text", "content", "input_text", "body"):
            if k in v:
                return _flatten(v[k])
    return []


def content_digest(data) -> tuple[str | None, list[str] | None]:
    """(prompt_prefix_hash, content_hashes) from the bodies of a parser event payload, BEFORE drop_bodies.

    prompt_prefix_hash = sha256 hex of the first 4 KiB of the fixed prefix (`system`, else the first block of
    `prompt` / `messages` / `content`); content_hashes = `<sha256[:12]>:<tokens>` per block (tokens = the block's
    `tokens` when the parser gives it, else ceil(UTF-8 bytes / 4)). Only hashes leave this function; where the event
    carries no body the result is (None, None), never '' or []."""
    if not isinstance(data, dict):
        return None, None
    blocks: list[str] = []
    counts: list[int | None] = []
    for k in ("prompt", "messages", "content"):
        v = data.get(k)
        items = v if isinstance(v, (list, tuple)) else [v]
        for b in items:
            for t in _flatten(b):
                blocks.append(t)
                n = b.get("tokens") if isinstance(b, dict) else None
                counts.append(n if isinstance(n, int) and not isinstance(n, bool) and n >= 0 else None)
        if blocks:
            break
    system = _flatten(data.get("system"))
    prefix = "".join(system) if system else (blocks[0] if blocks else "")
    prefix_hash = hashlib.sha256(prefix.encode()[:PREFIX_BYTES]).hexdigest() if prefix else None
    hashes = []
    for t, n in zip(blocks, counts):
        raw = t.encode()
        hashes.append(f"{hashlib.sha256(raw).hexdigest()[:12]}:{n if n is not None else -(-len(raw) // 4)}")
    return prefix_hash, hashes or None

"""Secret scrub table (data-model.md 4.1). Applied to body text only when profiles.store_bodies is on; by default
bodies are dropped (see adapters/common.py). Replacement is `[REDACTED:<kind>]`."""
from __future__ import annotations

import re

# Order matters: specific shapes first, the generic high-entropy rule last.
PATTERNS: tuple[tuple[str, re.Pattern], ...] = (
    ("private_key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?(?:-----END [A-Z ]*PRIVATE KEY-----|\Z)", re.S)),
    ("anthropic_key", re.compile(r"sk-ant-[A-Za-z0-9_\-]{8,}")),
    ("openai_key", re.compile(r"sk-(?:proj-)?[A-Za-z0-9_\-]{16,}")),
    ("google_key", re.compile(r"AIza[0-9A-Za-z_\-]{20,}")),
    ("github_token", re.compile(r"(?:ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})")),
    ("aws_key", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("slack_token", re.compile(r"xox[abpr]-[A-Za-z0-9\-]{10,}")),
    ("jwt", re.compile(r"eyJ[A-Za-z0-9_\-]+\.eyJ[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]*")),
    ("assignment", re.compile(r"(?i)\b(password|passwd|token|secret)\s*=\s*[^\s&;\"']+")),
    ("high_entropy", re.compile(r"(?<![A-Za-z0-9+/_\-])(?=[A-Za-z0-9+/_\-]{32,})(?=\S*[A-Za-z])(?=\S*\d)[A-Za-z0-9+/_\-]{32,}(?![A-Za-z0-9+/_\-])")),
)


def scrub_text(text: str) -> str:
    for kind, rx in PATTERNS:
        if kind == "assignment":
            text = rx.sub(lambda m: f"{m.group(1)}=[REDACTED:{kind}]", text)
        else:
            text = rx.sub(f"[REDACTED:{kind}]", text)
    return text


def scrub_value(v):
    """Scrub every string inside a nested dict/list structure."""
    if isinstance(v, str):
        return scrub_text(v)
    if isinstance(v, dict):
        return {k: scrub_value(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [scrub_value(x) for x in v]
    return v

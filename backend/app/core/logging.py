"""Log redaction filter: removes the secret patterns of docs/data-model.md 4.1 from every record."""
from __future__ import annotations

import logging
import re

PATTERNS: tuple[tuple[str, re.Pattern], ...] = (
    ("private_key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----(?:.*?-----END [A-Z ]*PRIVATE KEY-----)?", re.S)),
    ("anthropic_key", re.compile(r"sk-ant-[A-Za-z0-9_\-]{8,}")),
    ("openai_key", re.compile(r"sk-[A-Za-z0-9_\-]{16,}")),
    ("google_key", re.compile(r"AIza[0-9A-Za-z_\-]{20,}")),
    ("github_token", re.compile(r"(?:ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})")),
    ("aws_key", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("slack_token", re.compile(r"xox[abpr]-[A-Za-z0-9\-]{10,}")),
    ("jwt", re.compile(r"eyJ[A-Za-z0-9_\-]+\.eyJ[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]*")),
    ("assignment", re.compile(r"(?i)\b((?:password|token|secret)\s*=\s*)[^\s&;,\"']+")),
    ("high_entropy", re.compile(r"(?<![A-Za-z0-9+/=_\-])[A-Za-z0-9+/_\-]{32,}={0,2}(?![A-Za-z0-9+/=_\-])")),
)


def redact(text: str) -> str:
    for kind, pat in PATTERNS:
        if kind == "assignment":
            text = pat.sub(lambda m: f"{m.group(1)}[REDACTED:{kind}]", text)
        else:
            text = pat.sub(f"[REDACTED:{kind}]", text)
    return text


class RedactionFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = redact(record.getMessage())
        record.args = None
        if record.exc_info and record.exc_info[1] is not None:
            record.exc_text = redact(logging.Formatter().formatException(record.exc_info))
            record.exc_info = None
        return True


def install(logger: logging.Logger | None = None) -> None:
    """Attach to the root logger's handlers (filters on loggers don't cover propagated records)."""
    root = logger or logging.getLogger()
    f = RedactionFilter()
    root.addFilter(f)
    for h in root.handlers:
        h.addFilter(f)

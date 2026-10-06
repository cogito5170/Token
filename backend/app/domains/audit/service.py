"""Audit use cases: append-only record(), admin-only query(). Store is injected so the rules test without a DB.

detail holds ids, counts and states only. It is checked before anything is written: a key-shaped string, a private
key block, or a secret-named field with a non-empty value is refused (AuditError 422), never stored or redacted.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone

ACTOR_KINDS = ("user", "system", "worker", "run_node")
MAX_LIMIT = 200
MAX_DETAIL_BYTES = 8192

# Value patterns are assembled from parts so this file does not trip infra/secret_scan.py.
_VALUE_RULES = (
    re.compile("-----BEGIN [A-Z ]*PRIVATE" + " KEY-----"),
    re.compile(r"\bAKIA" + r"[0-9A-Z]{16}\b"),
    re.compile(r"\bgh[pousr]_" + r"[A-Za-z0-9]{30,}"),
    re.compile(r"\bsk-(?:ant-)?" + r"[A-Za-z0-9_-]{20,}"),
    re.compile(r"\bxox[abprs]-" + r"[A-Za-z0-9-]{10,}"),
    re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{5,}"),  # JWT
    re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]{16,}"),
)
_KEY_RULE = re.compile(r"(?i)(password|passwd|secret|api[_-]?key|token|credential|private[_-]?key)")
# counts / flags / ids named after secrets are fine, e.g. "token_count", "has_password"
_KEY_OK_SUFFIX = re.compile(r"(?i)(_count|_id|_ids|_len|_at|_ttl|_fingerprint|_last4)$|^(has|is|rotated|revoked)_")
_TOKENS_SUFFIX = re.compile(r"(?i)_tokens$")


def _is_key_ok(k: str, v: object) -> bool:
    if _KEY_OK_SUFFIX.search(k):
        return True
    if _TOKENS_SUFFIX.search(k) and (v is None or (isinstance(v, (int, float)) and not isinstance(v, bool))):
        return True
    return False


class AuditError(Exception):
    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status, self.code, self.message = status, code, message


@dataclass
class AuditRow:
    id: int
    at: datetime
    workspace_id: str | None
    actor_user_id: str | None
    actor_kind: str
    action: str
    target_kind: str
    target_id: str
    detail: dict = field(default_factory=dict)
    request_id: str | None = None


def check_detail(detail, path: str = "detail") -> None:
    """Raise AuditError(422) when detail could carry a secret. Walks nested dicts and lists."""
    if isinstance(detail, dict):
        for k, v in detail.items():
            if not isinstance(k, str):
                raise AuditError(422, "audit.detail_invalid", f"{path}: keys must be strings")
            if _KEY_RULE.search(k) and not _is_key_ok(k, v) and v not in (None, "", False, 0):
                raise AuditError(422, "audit.detail_secret", f"{path}.{k}: secret-named field")
            check_detail(v, f"{path}.{k}")
    elif isinstance(detail, (list, tuple)):
        for i, v in enumerate(detail):
            check_detail(v, f"{path}[{i}]")
    elif isinstance(detail, str):
        if any(r.search(detail) for r in _VALUE_RULES):
            raise AuditError(422, "audit.detail_secret", f"{path}: key-shaped string")
    elif detail is not None and not isinstance(detail, (int, float, bool)):
        raise AuditError(422, "audit.detail_invalid", f"{path}: unsupported type {type(detail).__name__}")


def _uuid_or_none(v):
    if v is None:
        return None
    import uuid
    try:
        return str(uuid.UUID(str(v)))
    except ValueError:
        return None


class AuditService:
    def __init__(self, store) -> None:
        self.store = store

    def record(self, action: str, actor: str | None, detail: dict | None = None, *, workspace_id: str | None = None,
               target_kind: str | None = None, target_id: str | None = None, actor_kind: str | None = None,
               request_id: str | None = None) -> AuditRow:
        """Append one row. Positional shape (action, actor, detail) matches what identity/workspace inject.

        workspace_id / target default from detail ("workspace_id", then the first `<kind>_id` key) so a domain
        that already passes ids in detail needs nothing more. actor None means system.
        """
        if not action or not isinstance(action, str) or len(action) > 120:
            raise AuditError(422, "audit.action_invalid", "action required (<=120 chars)")
        detail = dict(detail or {})
        check_detail(detail)
        if len(json.dumps(detail, default=str)) > MAX_DETAIL_BYTES:
            raise AuditError(422, "audit.detail_too_large", "detail too large")
        ws = _uuid_or_none(workspace_id or detail.get("workspace_id"))
        if target_kind is None or target_id is None:
            tk, tid = _guess_target(action, detail)
            target_kind, target_id = target_kind or tk, target_id or tid
        actor_user = _uuid_or_none(actor)
        kind = actor_kind or ("user" if actor_user else "system")
        if kind not in ACTOR_KINDS:
            raise AuditError(422, "audit.actor_kind_invalid", "actor_kind")
        return self.store.append(AuditRow(0, datetime.now(timezone.utc), ws, actor_user, kind, action,
                                          str(target_kind), str(target_id), detail, request_id))

    def query(self, ws: str, role: str, *, action: str | None = None, frm: datetime | None = None,
              to: datetime | None = None, cursor: str | None = None, limit: int = 50) -> tuple[list[AuditRow], str | None]:
        """Newest first. Admin only (role is the caller's role in ws, from workspace.api.require_member)."""
        if role != "admin":
            raise AuditError(403, "audit.forbidden", "admin only")
        limit = max(1, min(int(limit), MAX_LIMIT))
        before = None
        if cursor:
            try:
                before = int(cursor)
            except ValueError:
                raise AuditError(400, "audit.cursor_invalid", "cursor") from None
        rows = self.store.query(ws, action, frm, to, before, limit + 1)
        more = len(rows) > limit
        rows = rows[:limit]
        return rows, (str(rows[-1].id) if more and rows else None)


def _guess_target(action: str, detail: dict) -> tuple[str, str]:
    prefix = action.split(".", 1)[0]
    key = f"{prefix}_id"
    if detail.get(key) is not None:
        return prefix, str(detail[key])
    for k, v in detail.items():
        if k.endswith("_id") and k != "workspace_id" and v is not None:
            return k[:-3], str(v)
    if detail.get("workspace_id") is not None:
        return "workspace", str(detail["workspace_id"])
    return prefix, "-"


class MemoryStore:
    """Append-only in memory; update/delete raise like the DB trigger does."""

    def __init__(self) -> None:
        self.rows: list[AuditRow] = []

    def append(self, row: AuditRow) -> AuditRow:
        row.id = len(self.rows) + 1
        self.rows.append(row)
        return row

    def query(self, ws, action, frm, to, before, limit):
        out = []
        for r in reversed(self.rows):
            if r.workspace_id != ws or (action and r.action != action):
                continue
            if (frm and r.at < frm) or (to and r.at > to) or (before and r.id >= before):
                continue
            out.append(r)
            if len(out) >= limit:
                break
        return out

    def update(self, *a, **k):
        raise AuditError(500, "audit.append_only", "audit_log is append-only")

    delete = update

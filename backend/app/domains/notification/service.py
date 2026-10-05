"""Notification use cases: in-app notifications, per-kind/channel prefs, event subscribers.

Kind = the event name that caused it. A recipient is `user_id` in the payload, or every member of `workspace_id`.
Each event yields one notification per recipient; a disabled (kind, in_app) pref suppresses it (no pref = enabled).
Text is built from a fixed template plus ids and numbers only, never from free payload text (no keys, no prompts).
Store and member lookup are injected so the rules test without a DB.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable

CHANNELS = ("in_app", "email", "slack")
EVENT_KINDS = ("quota.alert.raised", "ingestion.job.finished", "ingestion.job.failed", "advisor.proposal.created")
MAX_LIST = 200

# kind -> (payload key used as ref, text template). Template fields come from `_safe` values only.
_TEMPLATES = {
    "quota.alert.raised": ("alert_id", "예산 경보: 임계 {threshold_pct}% 를 넘었습니다."),
    "ingestion.job.finished": ("job_id", "수집 작업이 끝났습니다."),
    "ingestion.job.failed": ("job_id", "수집 작업이 실패했습니다."),
    "advisor.proposal.created": ("proposal_id", "새 최적화 제안이 있습니다."),
}


class NotificationError(Exception):
    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status, self.code, self.message = status, code, message


@dataclass
class Notification:
    id: str
    user_id: str
    workspace_id: str | None
    kind: str
    ref: str | None
    text: str
    created_at: datetime
    read_at: datetime | None = None


class MemoryStore:
    def __init__(self) -> None:
        self.rows: list[Notification] = []
        self.prefs: dict[tuple[str, str, str], bool] = {}

    def add(self, n: Notification) -> Notification:
        self.rows.append(n)
        return n

    def list(self, user_id: str, unread: bool, limit: int) -> list[Notification]:
        rows = [n for n in self.rows if n.user_id == user_id and (not unread or n.read_at is None)]
        return sorted(rows, key=lambda n: n.created_at, reverse=True)[:limit]

    def mark_read(self, user_id: str, nid: str, at: datetime) -> bool:
        for n in self.rows:
            if n.id == nid and n.user_id == user_id:
                if n.read_at is None:
                    n.read_at = at
                return True
        return False

    def get_prefs(self, user_id: str) -> list[tuple[str, str, bool]]:
        return sorted((k, c, e) for (u, k, c), e in self.prefs.items() if u == user_id)

    def put_prefs(self, user_id: str, prefs: list[tuple[str, str, bool]]) -> None:
        for k, c, e in prefs:
            self.prefs[(user_id, k, c)] = e

    def enabled(self, user_id: str, kind: str, channel: str) -> bool:
        return self.prefs.get((user_id, kind, channel), True)


def _uuid(v) -> str | None:
    try:
        return str(uuid.UUID(str(v)))
    except (ValueError, TypeError):
        return None


def _ref(v) -> str | None:
    return str(v)[:100] if isinstance(v, (str, int)) and not isinstance(v, bool) else None


class NotificationService:
    def __init__(self, store, members: Callable[[str], list[str]] | None = None,
                 clock: Callable[[], datetime] | None = None) -> None:
        self.store = store
        self._members = members or (lambda ws: [])
        self._now = clock or (lambda: datetime.now(timezone.utc))

    # ---- public interface (docs/domain-model.md)
    def notify(self, kind: str, ref: str | None, text: str, *, user_id: str | None = None,
               workspace_id: str | None = None) -> list[Notification]:
        """One notification per recipient (user_id, else every member of workspace_id), minus those who disabled in_app."""
        if not kind or not text:
            raise NotificationError(422, "notification.invalid", "kind and text are required")
        users = [user_id] if user_id else list(dict.fromkeys(self._members(workspace_id) if workspace_id else []))
        out = []
        for u in users:
            if not self.store.enabled(u, kind, "in_app"):
                continue
            out.append(self.store.add(Notification(str(uuid.uuid4()), u, workspace_id, kind, ref, text, self._now())))
        return out

    def list(self, user_id: str, unread: bool = False, limit: int = 50) -> list[Notification]:
        return self.store.list(user_id, bool(unread), max(1, min(int(limit), MAX_LIST)))

    def mark_read(self, user_id: str, nid: str) -> None:
        """404 for an unknown id or someone else's notification. Marking twice keeps the first read_at."""
        if _uuid(nid) is None or not self.store.mark_read(user_id, _uuid(nid), self._now()):
            raise NotificationError(404, "notification.not_found", "notification not found")

    def get_prefs(self, user_id: str) -> list[dict]:
        """Stored prefs plus the default (enabled) in_app row for each subscribed kind not stored yet."""
        have = {(k, c): e for k, c, e in self.store.get_prefs(user_id)}
        for k in EVENT_KINDS:
            have.setdefault((k, "in_app"), True)
        return [{"kind": k, "channel": c, "enabled": e} for (k, c), e in sorted(have.items())]

    def put_prefs(self, user_id: str, prefs: list[dict]) -> list[dict]:
        rows = []
        for p in prefs or []:
            if not isinstance(p, dict) or not isinstance(p.get("kind"), str) or not p["kind"] \
                    or p.get("channel") not in CHANNELS or not isinstance(p.get("enabled"), bool):
                raise NotificationError(422, "notification.pref_invalid", "each pref needs kind, channel, enabled")
            rows.append((p["kind"], p["channel"], p["enabled"]))
        self.store.put_prefs(user_id, rows)
        return self.get_prefs(user_id)

    # ---- event subscribers: handler(name, payload)
    def on_event(self, name: str, payload: dict) -> list[Notification]:
        spec = _TEMPLATES.get(name)
        if spec is None:
            return []
        ref_key, template = spec
        user = _uuid(payload.get("user_id"))
        ws = _uuid(payload.get("workspace_id"))
        if user is None and ws is None:
            return []  # nobody to tell
        pct = payload.get("threshold_pct")
        text = template.format(threshold_pct=pct if isinstance(pct, int) and not isinstance(pct, bool) else "-")
        return self.notify(name, _ref(payload.get(ref_key)), text, user_id=user, workspace_id=ws)

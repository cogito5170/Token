"""Synchronous in-process event bus. Names are <domain>.<noun>.<verb-past>; handlers run in subscription order."""
from __future__ import annotations

import logging
import re
from collections import defaultdict
from typing import Any, Callable

NAME_RE = re.compile(r"^[a-z]+\.[a-z_]+\.[a-z_]+$")
log = logging.getLogger(__name__)


class EventBus:
    def __init__(self) -> None:
        self._handlers: dict[str, list[Callable[[str, dict], Any]]] = defaultdict(list)

    def subscribe(self, name: str, handler: Callable[[str, dict], Any]) -> None:
        self._handlers[name].append(handler)

    def publish(self, name: str, payload: dict | None = None) -> int:
        if not NAME_RE.match(name):
            raise ValueError(f"bad event name: {name}")
        n = 0
        for h in list(self._handlers.get(name, ())):
            try:
                h(name, payload or {})
            except Exception:  # one failing handler never blocks the rest
                log.exception("event handler failed for %s", name)
            n += 1
        return n


bus = EventBus()

"""Format adapter registry. Adapters (CMD-GC23) register here; the pipeline only knows this protocol.

An adapter yields items from `parse`: ParsedCall for a good line, ParsedReject for a bad one (code only, never the
raw line), ParsedSession/ParsedTask for the optional load_calls side tables.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import BinaryIO, Iterable, Protocol

from app.domains.usage.api import CallIn, SessionIn, TaskIn


@dataclass
class ParsedCall:
    line_no: int
    call: CallIn


@dataclass
class ParsedReject:
    line_no: int
    code: str


@dataclass
class ParsedSession:
    key: str
    session: SessionIn


@dataclass
class ParsedTask:
    key: str
    task: TaskIn


class Adapter(Protocol):
    kind: str    # one of the source_kind values in the schema
    parser: str  # recorded in ingest_jobs.parser, e.g. 'telemetry.collect.from_cc_jsonl@f6c7ae2'

    def detect(self, filename: str, head: bytes) -> bool: ...
    def parse(self, f: BinaryIO) -> Iterable[object]: ...


_adapters: list[Adapter] = []


def register(adapter: Adapter) -> None:
    _adapters[:] = [a for a in _adapters if a.kind != adapter.kind] + [adapter]


def unregister(kind: str) -> None:
    _adapters[:] = [a for a in _adapters if a.kind != kind]


def adapters() -> list[Adapter]:
    return list(_adapters)

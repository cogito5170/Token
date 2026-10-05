"""Anthropic / OpenAI usage exports (CSV or JSON). Column map -> usage dict -> telemetry.usage.l0_usage(provider, u).
Only the column-name table lives here; CSV via stdlib csv, JSON via json.load of the whole document."""
from __future__ import annotations

import csv
import io
import json
from typing import BinaryIO, Iterable

from app.domains.ingestion import registry
from app.domains.usage.api import CallIn

from .common import dedupe, l0_tokens, to_dt

# export column name -> key of the usage dict handed to l0_usage (Anthropic Messages usage names; OpenAI
# usage-export names, with the older chat-completions spellings as aliases).
COLUMNS = {
    "anthropic": {"uncached_input_tokens": "input_tokens", "input_tokens": "input_tokens",
                  "cache_read_input_tokens": "cache_read_input_tokens",
                  "cache_creation_input_tokens": "cache_creation_input_tokens", "output_tokens": "output_tokens"},
    # OpenAI: dotted target = nested details dict (l0_usage reads prompt_tokens_details.cached_tokens etc.)
    "openai": {"input_tokens": "prompt_tokens", "prompt_tokens": "prompt_tokens",
               "input_cached_tokens": "prompt_tokens_details.cached_tokens",
               "cached_tokens": "prompt_tokens_details.cached_tokens",
               "output_tokens": "completion_tokens", "completion_tokens": "completion_tokens",
               "reasoning_tokens": "completion_tokens_details.reasoning_tokens"},
}
MODEL_COLS = ("model", "model_id", "snapshot_id")
TIME_COLS = ("starting_at", "start_time", "date", "bucket_start", "timestamp")
KEY_COLS = ("api_key_id", "api_key", "project_id", "workspace_id")
COST_COLS = ("cost_usd", "amount", "cost")


def _num(v):
    try:
        return int(float(v)) if v not in (None, "") else None
    except (TypeError, ValueError):
        return None


class ExportAdapter:
    parser = "csv/json column map -> telemetry.usage.l0_usage@f6c7ae2"

    def __init__(self, provider: str, kind: str):
        self.provider, self.kind = provider, kind

    def detect(self, filename: str, head: bytes) -> bool:
        if not filename.endswith((".csv", ".json")):
            return False
        text = head.decode("utf-8", "ignore").lower()
        needles = (("uncached_input_tokens", "cache_creation") if self.provider == "anthropic"
                   else ("n_context_tokens_total", "input_cached_tokens", "num_model_requests", "prompt_tokens"))
        return any(n in text for n in needles)

    def _rows(self, f: BinaryIO, filename_hint: bytes):
        raw = f.read()
        text = raw.decode("utf-8-sig")
        if text.lstrip().startswith(("[", "{")):
            doc = json.loads(text)
            rows = doc if isinstance(doc, list) else doc.get("data") or doc.get("results") or []
            return [r for b in rows for r in (b.get("results", [b]) if isinstance(b, dict) else [b])]
        return list(csv.DictReader(io.StringIO(text)))

    def parse(self, f: BinaryIO) -> Iterable[object]:
        from telemetry.usage import l0_usage
        try:
            rows = self._rows(f, b"")
        except (ValueError, UnicodeDecodeError):
            yield registry.ParsedReject(1, "bad_file")
            return
        cmap = COLUMNS[self.provider]
        for n, row in enumerate(rows, start=1):
            if not isinstance(row, dict):
                yield registry.ParsedReject(n, "bad_row")
                continue
            u: dict = {}
            for col, key in cmap.items():
                if row.get(col) not in (None, ""):
                    head, _, leaf = key.partition(".")
                    (u.setdefault(head, {}) if leaf else u)[leaf or head] = _num(row[col])
            model = next((row[c] for c in MODEL_COLS if row.get(c)), None)
            if not u or not model:
                yield registry.ParsedReject(n, "bad_row")
                continue
            fields, _null = l0_usage(self.provider, u)  # (fields dict, names the source gave as null); null stays None
            tok = l0_tokens(fields)
            at, basis = to_dt(next((row[c] for c in TIME_COLS if row.get(c)), None))
            key = next((row[c] for c in KEY_COLS if row.get(c)), "")
            cost = next((row[c] for c in COST_COLS if row.get(c) not in (None, "")), None)
            try:
                micro = round(float(cost) * 1_000_000) if cost is not None else None
            except ValueError:
                micro = None
            yield registry.ParsedCall(n, CallIn(
                model_id=model, provider=self.provider, source_kind=self.kind, occurred_at=at, time_basis=basis,
                call_index=None, role="aggregate", cost_provider_microusd=micro,
                dedupe_key=dedupe(self.kind, row.get(next((c for c in TIME_COLS if row.get(c)), ""), ""), model, key),
                **tok))


def anthropic_export() -> ExportAdapter:
    return ExportAdapter("anthropic", "anthropic_export")


def openai_export() -> ExportAdapter:
    return ExportAdapter("openai", "openai_export")

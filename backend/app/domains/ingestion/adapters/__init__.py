"""Format adapters; `register_all()` puts them in the ingestion registry (bodies dropped unless store_bodies)."""
from __future__ import annotations

from app.domains.ingestion import registry

from .claude_code import ClaudeCodeAdapter
from .exports import ExportAdapter, anthropic_export, openai_export
from .ga_l0 import GaL0Adapter


def register_all(store_bodies: bool = False, hasher=None) -> None:
    for a in (ClaudeCodeAdapter(store_bodies, hasher), GaL0Adapter(store_bodies), anthropic_export(), openai_export()):
        registry.register(a)

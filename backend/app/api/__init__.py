"""Router assembly: mounts each domain's router.py (CMD-GC12). Every route belongs to exactly one x-domain."""
from __future__ import annotations

import importlib

from fastapi import APIRouter

from app.domains import DOMAINS


def build_router() -> APIRouter:
    """Mount `app.domains.<d>.router.router` for every domain that has one (skeleton domains have none yet)."""
    root = APIRouter()
    for d in DOMAINS:
        try:
            mod = importlib.import_module(f"app.domains.{d}.router")
        except ModuleNotFoundError as e:
            if e.name == f"app.domains.{d}.router":
                continue
            raise
        root.include_router(mod.router)
    return root

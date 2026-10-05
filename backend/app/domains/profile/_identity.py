"""The one place this domain reaches identity: `identity.api.current_user`.

identity (CMD-GC13) has no api.py yet, only router.current_user. Until it re-exports it there (request to baseline),
fall back by dotted name so the boundary rule (public api only) keeps one switch point. Remove the fallback then.
"""
from __future__ import annotations

import importlib

try:
    current_user = importlib.import_module("app.domains.identity.api").current_user
except ModuleNotFoundError as e:
    if e.name != "app.domains.identity.api":
        raise
    current_user = importlib.import_module("app.domains.identity.router").current_user

"""identity.api: the public surface other domains import.

    from app.domains.identity.api import current_user
    def route(user=Depends(current_user)): ...      # 401 without a valid bearer access token
"""
from __future__ import annotations

from .router import current_user  # noqa: F401
from .service import AuthError  # noqa: F401

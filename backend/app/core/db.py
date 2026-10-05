"""psycopg connection pool, opened lazily so the app imports and /healthz works without a database."""
from __future__ import annotations

_pool = None


def open_pool(dsn: str, min_size: int = 1, max_size: int = 10):
    global _pool
    from psycopg_pool import ConnectionPool

    if _pool is None:
        _pool = ConnectionPool(dsn, min_size=min_size, max_size=max_size, open=True)
    return _pool


def get_pool():
    if _pool is None:
        raise RuntimeError("database pool is not open")
    return _pool


def close_pool() -> None:
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None

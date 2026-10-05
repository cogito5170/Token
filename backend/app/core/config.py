"""Settings come from environment variables; only their names live in code (values: .env, never committed)."""
ENV_VARS = (
    "DATABASE_URL",
    "GC_JWT_SECRET",
    "GC_KEK_ID",
    "TELEMETRY_HASH_KEY",
    "GC_UPLOAD_DIR",
    "GC_UPLOAD_MAX_BYTES",
    "GC_CORS_ORIGIN",
)
SECRET_ENV_VARS = ("DATABASE_URL", "GC_JWT_SECRET", "TELEMETRY_HASH_KEY")


import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    database_url: str | None
    jwt_secret: str | None
    upload_dir: str
    upload_max_bytes: int
    cors_origin: str | None

    def __repr__(self) -> str:  # never show secret values
        return "Settings(<redacted>)"


def load_settings(env=None) -> Settings:
    e = os.environ if env is None else env
    return Settings(
        database_url=e.get("DATABASE_URL"),
        jwt_secret=e.get("GC_JWT_SECRET"),
        upload_dir=e.get("GC_UPLOAD_DIR", "/tmp/gc-uploads"),
        upload_max_bytes=int(e.get("GC_UPLOAD_MAX_BYTES", str(200 * 1024 * 1024))),
        cors_origin=e.get("GC_CORS_ORIGIN"),
    )

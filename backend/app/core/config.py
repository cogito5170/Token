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

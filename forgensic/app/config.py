import os
from pathlib import Path

APP_ENV = os.getenv("APP_ENV", "prod")
DATA_DIR = Path(os.getenv("DATA_DIR", "/app/forgensic_data"))
MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_BYTES", str(25 * 1024 * 1024)))
FINDINGS_MAX_PER_PAGE = int(os.getenv("FINDINGS_MAX_PER_PAGE", "5"))
FINDINGS_MIN_AREA_RATIO = float(os.getenv("FINDINGS_MIN_AREA_RATIO", "0.003"))
JOB_TTL_SECONDS = int(os.getenv("JOB_TTL_SECONDS", "3600"))
CORS_ORIGINS = [origin.strip() for origin in os.getenv("CORS_ORIGINS", "*").split(",") if origin.strip()]

OCR_ENABLED = os.getenv("OCR_ENABLED", "true").lower() == "true"

PIPELINE_PRESET = os.getenv("PIPELINE_PRESET", "npv_focus")
PIPELINE_VERSION = os.getenv("PIPELINE_VERSION", "ps3-cv-1.0.0")

# ── Redis / Celery ─────────────────────────────────────────────────────────────
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

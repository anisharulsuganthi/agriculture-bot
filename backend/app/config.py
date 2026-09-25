"""
Centralised configuration (Phase 1).

Every environment dependent value lives here. Nothing else in the codebase may
hardcode a path, URL, key, limit or host. Values are read from the process
environment, optionally seeded by ``backend/.env`` (never committed).

Real secrets must never be written into this file.
"""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import List

try:  # python-dotenv is a declared dependency; keep a graceful fallback
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover
    def load_dotenv(*_args, **_kwargs):  # type: ignore
        return False

# backend/app/config.py -> app -> backend -> project root
BACKEND_DIR: Path = Path(__file__).resolve().parents[1]
PROJECT_ROOT: Path = BACKEND_DIR.parent

load_dotenv(BACKEND_DIR / ".env")


def _str(name: str, default: str = "") -> str:
    value = os.getenv(name)
    return default if value is None or value.strip() == "" else value.strip()


def _int(name: str, default: int) -> int:
    try:
        return int(str(os.getenv(name, default)).strip())
    except (TypeError, ValueError):
        return default


def _float(name: str, default: float) -> float:
    try:
        return float(str(os.getenv(name, default)).strip())
    except (TypeError, ValueError):
        return default


def _bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _list(name: str, default: List[str]) -> List[str]:
    raw = os.getenv(name)
    if not raw or not raw.strip():
        return list(default)
    return [item.strip() for item in raw.split(",") if item.strip()]


class Settings:
    """Resolved application settings (immutable snapshot per process)."""

    # ---- application -------------------------------------------------
    app_name = "Smart Farm - AI-Powered Agricultural Decision Intelligence System"
    app_version = "2.0.0"
    app_env = _str("APP_ENV", "development")
    api_host = _str("API_HOST", "0.0.0.0")
    api_port = _int("API_PORT", 8000)
    frontend_url = _str("FRONTEND_URL", "http://localhost:5500")
    api_base_url = _str("API_BASE_URL", "http://localhost:8000")

    # ---- database ----------------------------------------------------
    database_path = Path(_str("DATABASE_PATH", str(BACKEND_DIR / "database.db")))
    database_echo = _bool("DATABASE_ECHO", False)

    # ---- machine learning -------------------------------------------
    model_dir = Path(_str("MODEL_DIR", str(BACKEND_DIR / "models" / "plant_disease_model")))
    ml_device = _str("ML_DEVICE", "auto")                        # auto | cpu | cuda
    ml_top_k = _int("ML_TOP_K", 5)
    ml_confidence_floor = _float("ML_CONFIDENCE_FLOOR", 40.0)    # % below this -> "uncertain"
    ml_warmup_on_startup = _bool("ML_WARMUP_ON_STARTUP", True)

    # ---- uploads -----------------------------------------------------
    max_upload_bytes = _int("MAX_UPLOAD_BYTES", 8 * 1024 * 1024)  # 8 MB
    allowed_image_types = _list("ALLOWED_IMAGE_TYPES", ["image/jpeg", "image/png", "image/webp"])
    allowed_image_extensions = _list("ALLOWED_IMAGE_EXTENSIONS", [".jpg", ".jpeg", ".png", ".webp"])
    min_image_dimension = _int("MIN_IMAGE_DIMENSION", 32)
    max_image_pixels = _int("MAX_IMAGE_PIXELS", 25_000_000)       # decompression-bomb guard

    # ---- authentication ---------------------------------------------
    jwt_secret = _str("JWT_SECRET", "change-me-in-env-file")
    jwt_algorithm = _str("JWT_ALGORITHM", "HS256")
    access_token_expire_minutes = _int("ACCESS_TOKEN_EXPIRE_MINUTES", 720)
    # Transitional: allows the legacy X-User-Id header while the SPA migrates.
    allow_legacy_user_header = _bool("ALLOW_LEGACY_USER_HEADER", True)
    password_min_length = _int("PASSWORD_MIN_LENGTH", 6)
    otp_length = _int("OTP_LENGTH", 6)
    otp_expiry_minutes = _int("OTP_EXPIRY_MINUTES", 10)
    otp_max_attempts = _int("OTP_MAX_ATTEMPTS", 5)

    # ---- rate limiting ----------------------------------------------
    rate_limit_enabled = _bool("RATE_LIMIT_ENABLED", True)
    login_rate_limit = _int("LOGIN_RATE_LIMIT", 10)               # attempts / window / IP
    otp_rate_limit = _int("OTP_RATE_LIMIT", 5)
    rate_limit_window_seconds = _int("RATE_LIMIT_WINDOW_SECONDS", 300)

    # ---- CORS --------------------------------------------------------
    cors_origins = _list(
        "CORS_ORIGINS",
        [
            "http://localhost:5500",
            "http://127.0.0.1:5500",
            "http://localhost:8000",
            "http://127.0.0.1:8000",
        ],
    )

    # ---- weather -----------------------------------------------------
    openweather_api_key = _str("OPENWEATHER_API_KEY", "")
    openweather_base_url = _str("OPENWEATHER_BASE_URL", "https://api.openweathermap.org/data/2.5")
    weather_timeout_seconds = _int("WEATHER_TIMEOUT_SECONDS", 10)
    # When the provider is unreachable the service falls back to clearly
    # labelled simulated values (allowed in development only).
    allow_simulated_weather = _bool("ALLOW_SIMULATED_WEATHER", True)

    # ---- notifications (SMTP) ---------------------------------------
    smtp_host = _str("SMTP_HOST", "smtp.gmail.com")
    smtp_port = _int("SMTP_PORT", 587)
    sender_email = _str("SENDER_EMAIL", "")
    sender_app_password = _str("EMAIL_APP_PASSWORD", "")
    email_enabled = _bool("EMAIL_ENABLED", True)

    # ---- knowledge / RAG (Phase 4-5) --------------------------------
    knowledge_base_dir = Path(_str("KNOWLEDGE_BASE_DIR", str(PROJECT_ROOT / "data" / "knowledge_base")))
    vector_store_dir = Path(_str("VECTOR_STORE_DIR", str(PROJECT_ROOT / "data" / "vector_store")))
    embedding_model = _str("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
    rag_top_k = _int("RAG_TOP_K", 4)
    rag_min_score = _float("RAG_MIN_SCORE", 0.25)
    llm_provider = _str("LLM_PROVIDER", "extractive")     # extractive | openai_compatible | local
    llm_api_key = _str("LLM_API_KEY", _str("GROK_API_KEY", ""))
    llm_base_url = _str("LLM_BASE_URL", "https://api.x.ai/v1")
    llm_model = _str("LLM_MODEL", "grok-2-latest")
    llm_timeout_seconds = _int("LLM_TIMEOUT_SECONDS", 45)

    # ---- data quality ------------------------------------------------
    # Legacy rows have user_id = NULL. The Phase 1 migration assigns them to
    # this account so the demo data stays visible; empty = lowest-id user.
    legacy_data_owner_email = _str("LEGACY_DATA_OWNER_EMAIL", "")

    # ---- logging -----------------------------------------------------
    log_level = _str("LOG_LEVEL", "INFO").upper()
    log_dir = Path(_str("LOG_DIR", str(BACKEND_DIR / "logs")))

    @property
    def database_url(self) -> str:
        return f"sqlite:///{self.database_path.as_posix()}"

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() in {"production", "prod"}

    def as_public_dict(self) -> dict:
        """Settings safe to expose in docs / health output (never secrets)."""
        return {
            "app_env": self.app_env,
            "app_version": self.app_version,
            "database_path": str(self.database_path),
            "model_dir": str(self.model_dir),
            "ml_device": self.ml_device,
            "ml_top_k": self.ml_top_k,
            "llm_provider": self.llm_provider,
            "legacy_header_auth": self.allow_legacy_user_header,
            "cors_origins": self.cors_origins,
        }


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


settings = get_settings()


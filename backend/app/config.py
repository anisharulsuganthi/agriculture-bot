"""
Centralised configuration (Phase 1).

Every environment dependent value lives here. Nothing else in the codebase may
hardcode a path, URL, key, limit or host. Values are read from the process
environment, optionally seeded by ``backend/.env`` (never committed).

Real secrets must never be written into this file.
"""
from __future__ import annotations

import os
import secrets
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


def _path(name: str, default: Path) -> Path:
    """
    Resolve a configured path.

    Relative values are anchored to the **project root**, never to the current
    working directory, so the app behaves identically however it is started
    (``python main.py``, ``uvicorn main:app``, pytest, IDE runner).
    """
    raw = _str(name, "")
    candidate = Path(raw).expanduser() if raw else default
    if not candidate.is_absolute():
        candidate = PROJECT_ROOT / candidate
    return candidate.resolve()


class Settings:
    """
    Resolved application settings.

    Values are read from the environment **when an instance is created**, not when
    this module is imported, so tests can build a Settings object for an
    alternative environment without reloading the process. The application uses
    the single cached instance returned by :func:`get_settings`.
    """

    #: Identity of the build. Overridable per instance, not from the environment.
    app_name = "Smart Farm - AI-Powered Agricultural Decision Intelligence System"
    app_version = "2.0.0"

    def __init__(self) -> None:
        # ---- application ---------------------------------------------
        self.app_env = _str("APP_ENV", "development")
        # Loopback by default: the API is a local-first application and must not
        # be exposed on the LAN unless the operator opts in via API_HOST.
        self.api_host = _str("API_HOST", "127.0.0.1")
        self.api_port = _int("API_PORT", 8000)
        self.frontend_url = _str("FRONTEND_URL", "http://localhost:5500")
        self.api_base_url = _str("API_BASE_URL", "http://localhost:8000")

        # ---- database -------------------------------------------------
        self.database_path = _path("DATABASE_PATH", BACKEND_DIR / "database.db")
        self.database_echo = _bool("DATABASE_ECHO", False)
        self.database_enable_foreign_keys = _bool("DATABASE_ENABLE_FOREIGN_KEYS", True)

        # ---- machine learning ----------------------------------------
        self.model_dir = _path("MODEL_DIR", BACKEND_DIR / "models" / "plant_disease_model")
        _default_finetuned = (BACKEND_DIR / "models" / "plant_disease_model" / "best_plant_model.pth")
        if not _default_finetuned.is_file() and (PROJECT_ROOT.parent / "best_plant_model.pth").is_file():
            _default_finetuned = PROJECT_ROOT.parent / "best_plant_model.pth"
        self.finetuned_model_path = _path("FINETUNED_MODEL_PATH", _default_finetuned)

        _default_id2label = (BACKEND_DIR / "models" / "plant_disease_model" / "id2label.json")
        if not _default_id2label.is_file() and (PROJECT_ROOT.parent / "id2label.json").is_file():
            _default_id2label = PROJECT_ROOT.parent / "id2label.json"
        self.id2label_path = _path("ID2LABEL_PATH", _default_id2label)
        self.ml_device = _str("ML_DEVICE", "auto")                        # auto | cpu | cuda
        self.ml_top_k = _int("ML_TOP_K", 5)
        self.ml_confidence_floor = _float("ML_CONFIDENCE_FLOOR", 40.0)    # % below this -> "uncertain"
        self.ml_warmup_on_startup = _bool("ML_WARMUP_ON_STARTUP", True)
        # Ensemble: registry ids are declared in ml_service.MODEL_REGISTRY.
        self.ml_default_models = _str("ML_DEFAULT_MODELS", "mobilenetv2_finetuned")  # used when the request selects none
        self.ml_parallel = _bool("ML_PARALLEL", True)                      # concurrent inference on CPU

        # ---- uploads --------------------------------------------------
        self.max_upload_bytes = _int("MAX_UPLOAD_BYTES", 8 * 1024 * 1024)  # 8 MB
        self.allowed_image_types = _list(
            "ALLOWED_IMAGE_TYPES", ["image/jpeg", "image/png", "image/webp"]
        )
        self.allowed_image_extensions = _list(
            "ALLOWED_IMAGE_EXTENSIONS", [".jpg", ".jpeg", ".png", ".webp"]
        )
        self.min_image_dimension = _int("MIN_IMAGE_DIMENSION", 32)
        self.max_image_pixels = _int("MAX_IMAGE_PIXELS", 25_000_000)       # decompression-bomb guard

        # ---- authentication ------------------------------------------
        self.jwt_secret = _str("JWT_SECRET", "")
        self.jwt_secret_is_ephemeral = False
        self.jwt_algorithm = _str("JWT_ALGORITHM", "HS256")
        self.access_token_expire_minutes = _int("ACCESS_TOKEN_EXPIRE_MINUTES", 720)
        # The Version-1 ``X-User-Id`` header is a spoofable identity claim and is
        # therefore OFF unless an operator explicitly re-enables it. Every use is
        # logged as a warning so the cutover can be verified.
        self.allow_legacy_user_header = _bool("ALLOW_LEGACY_USER_HEADER", False)
        self.password_min_length = _int("PASSWORD_MIN_LENGTH", 8)
        self.otp_length = _int("OTP_LENGTH", 6)
        self.otp_expiry_minutes = _int("OTP_EXPIRY_MINUTES", 10)
        self.otp_max_attempts = _int("OTP_MAX_ATTEMPTS", 5)

        # ---- rate limiting --------------------------------------------
        self.rate_limit_enabled = _bool("RATE_LIMIT_ENABLED", True)
        self.login_rate_limit = _int("LOGIN_RATE_LIMIT", 10)               # attempts / window / IP
        self.register_rate_limit = _int("REGISTER_RATE_LIMIT", 20)
        self.forgot_rate_limit = _int("FORGOT_RATE_LIMIT", 5)
        self.reset_rate_limit = _int("RESET_RATE_LIMIT", 10)
        self.notify_rate_limit = _int("NOTIFY_RATE_LIMIT", 5)
        self.rate_limit_window_seconds = _int("RATE_LIMIT_WINDOW_SECONDS", 300)
        # X-Forwarded-For is client controlled: only honour it behind a trusted proxy.
        self.trust_proxy_headers = _bool("TRUST_PROXY_HEADERS", False)

        # ---- CORS ------------------------------------------------------
        self.cors_origins = _list(
            "CORS_ORIGINS",
            [
                "http://localhost:5500",
                "http://127.0.0.1:5500",
                "http://localhost:8000",
                "http://127.0.0.1:8000",
            ],
        )

        # ---- weather ---------------------------------------------------
        self.openweather_api_key = _str("OPENWEATHER_API_KEY", "")
        self.openweather_base_url = _str("OPENWEATHER_BASE_URL", "https://api.openweathermap.org/data/2.5")
        self.weather_timeout_seconds = _int("WEATHER_TIMEOUT_SECONDS", 10)
        # When the provider is unreachable the service falls back to clearly
        # labelled simulated values. Allowed in development, refused in production.
        self.allow_simulated_weather = _bool(
            "ALLOW_SIMULATED_WEATHER", self.app_env.lower() not in {"production", "prod"}
        )

        # ---- notifications (SMTP) -------------------------------------
        self.smtp_host = _str("SMTP_HOST", "smtp.gmail.com")
        self.smtp_port = _int("SMTP_PORT", 587)
        self.sender_email = _str("SENDER_EMAIL", "")
        self.sender_app_password = _str("EMAIL_APP_PASSWORD", "")
        self.email_enabled = _bool("EMAIL_ENABLED", True)

        # ---- knowledge / RAG (Phase 4-5) ------------------------------
        self.knowledge_base_dir = _path("KNOWLEDGE_BASE_DIR", PROJECT_ROOT / "data" / "knowledge_base")
        self.vector_store_dir = _path("VECTOR_STORE_DIR", PROJECT_ROOT / "data" / "vector_store")
        self.embedding_model = _str("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
        self.rag_top_k = _int("RAG_TOP_K", 4)
        self.rag_min_score = _float("RAG_MIN_SCORE", 0.25)
        self.llm_provider = _str("LLM_PROVIDER", "extractive")  # extractive | openai_compatible | local
        self.llm_api_key = _str("LLM_API_KEY", "")
        self.llm_base_url = _str("LLM_BASE_URL", "")
        self.llm_model = _str("LLM_MODEL", "")
        self.llm_timeout_seconds = _int("LLM_TIMEOUT_SECONDS", 45)

        # ---- data quality ----------------------------------------------
        # Legacy rows have user_id = NULL. The Phase 1 migration assigns them to
        # this account so the demo data stays visible; empty = lowest-id user.
        self.legacy_data_owner_email = _str("LEGACY_DATA_OWNER_EMAIL", "")

        # ---- logging ----------------------------------------------------
        self.log_level = _str("LOG_LEVEL", "INFO").upper()
        self.log_dir = _path("LOG_DIR", BACKEND_DIR / "logs")

    @property
    def database_url(self) -> str:
        return f"sqlite:///{self.database_path.as_posix()}"

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() in {"production", "prod"}

    @property
    def uses_default_jwt_secret(self) -> bool:
        return not self.jwt_secret or self.jwt_secret_is_ephemeral

    def validate_startup(self) -> List[str]:
        """
        Return configuration problems that must be fixed before production use.

        Development keeps working with a generated ephemeral secret (tokens are
        then simply invalid after a restart), but production must not start on
        an implicit secret.
        """
        problems: List[str] = []
        if self.uses_default_jwt_secret:
            problems.append(
                "JWT_SECRET is not set - every restart invalidates issued tokens. "
                "Set a long random value in backend/.env before any deployment."
            )
        if self.is_production and self.allow_legacy_user_header:
            problems.append("ALLOW_LEGACY_USER_HEADER must be false in production (X-User-Id is spoofable).")
        if self.is_production and self.allow_simulated_weather:
            problems.append("ALLOW_SIMULATED_WEATHER must be false in production.")
        if self.is_production and self.api_host == "0.0.0.0" and not self.trust_proxy_headers:
            problems.append("API_HOST=0.0.0.0 in production without TRUST_PROXY_HEADERS exposes the API directly.")
        return problems

    def as_public_dict(self) -> dict:
        """
        Settings safe to expose over HTTP (never secrets).

        Absolute filesystem paths are intentionally omitted: they are only useful
        to an operator and they describe the host layout to any caller.
        """
        return {
            "app_env": self.app_env,
            "app_version": self.app_version,
            "ml_device": self.ml_device,
            "ml_top_k": self.ml_top_k,
            "ml_confidence_floor": self.ml_confidence_floor,
            "ml_default_models": self.ml_default_models,
            "ml_parallel": self.ml_parallel,
            "llm_provider": self.llm_provider,
            "legacy_header_auth": self.allow_legacy_user_header,
            "cors_origins": self.cors_origins,
            "rate_limit_enabled": self.rate_limit_enabled,
        }


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    resolved = Settings()
    if resolved.uses_default_jwt_secret:
        # Never fall back to a hard-coded secret. An ephemeral per-process secret
        # keeps local development working (tokens simply stop working after a
        # restart) and is reported by validate_startup() for production.
        resolved.jwt_secret = secrets.token_urlsafe(48)
        resolved.jwt_secret_is_ephemeral = True
    return resolved


settings = get_settings()


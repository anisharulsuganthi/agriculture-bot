"""
Logging configuration (Phase 1).

Console + rotating file logging with automatic redaction of any registered
secret so tokens, API keys and passwords can never reach the log files.
"""
from __future__ import annotations

import logging
import logging.handlers
import re

from app.config import settings

_REDACTED = "***REDACTED***"
_secrets: set[str] = set()

_SECRET_PATTERNS = [
    # bearer tokens / JWTs
    re.compile(r"(?i)\beyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{5,}"),
    # api keys that look like provider keys
    re.compile(r"(?i)\b(xai-|sk-)[A-Za-z0-9_\-]{8,}"),
]


def register_secret(value: str | None) -> None:
    """Remember a secret so it is scrubbed from every future log record."""
    if value and len(value) >= 6:
        _secrets.add(value)


def redact(text: str) -> str:
    if not isinstance(text, str):
        return text
    for secret in _secrets:
        if secret in text:
            text = text.replace(secret, _REDACTED)
    for pattern in _SECRET_PATTERNS:
        text = pattern.sub(_REDACTED, text)
    return text


class RedactingFilter(logging.Filter):
    """Scrubs secrets from the message and its arguments."""

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            rendered = record.getMessage()
            cleaned = redact(rendered)
            if cleaned != rendered:
                record.msg = cleaned
                record.args = ()
        except Exception:  # pragma: no cover - never break logging
            pass
        return True


def setup_logging() -> logging.Logger:
    """Idempotently configure application logging and return the app logger."""
    for secret in (
        settings.jwt_secret,
        settings.openweather_api_key,
        settings.sender_app_password,
        settings.llm_api_key,
    ):
        register_secret(secret)

    logger = logging.getLogger("smartfarm")
    if getattr(logger, "_smartfarm_configured", False):
        return logger

    logger.setLevel(getattr(logging, settings.log_level, logging.INFO))
    logger.propagate = False

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    redacting_filter = RedactingFilter()

    console = logging.StreamHandler()
    console.setFormatter(formatter)
    console.addFilter(redacting_filter)
    logger.addHandler(console)

    try:
        settings.log_dir.mkdir(parents=True, exist_ok=True)
        file_handler = logging.handlers.RotatingFileHandler(
            settings.log_dir / "smartfarm.log",
            maxBytes=2_000_000,
            backupCount=3,
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        file_handler.addFilter(redacting_filter)
        logger.addHandler(file_handler)
    except OSError:  # pragma: no cover - read-only filesystem
        logger.warning("File logging unavailable; console logging only")

    logger._smartfarm_configured = True  # type: ignore[attr-defined]
    logger.debug("Logging initialised (level=%s, env=%s)", settings.log_level, settings.app_env)
    return logger


def get_logger(name: str = "smartfarm") -> logging.Logger:
    return logging.getLogger(name if name.startswith("smartfarm") else f"smartfarm.{name}")

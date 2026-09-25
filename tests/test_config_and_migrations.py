"""
Configuration, rate-limiting and migration tests (Phase 1 infrastructure).
"""
from __future__ import annotations

import importlib
import sqlite3

import pytest
from fastapi import HTTPException

from app import config as config_module
from app.config import Settings, get_settings, settings
from app.rate_limit import is_rate_limited, rate_limit, reset_rate_limits


# --------------------------------------------------------------------------
# configuration
# --------------------------------------------------------------------------
def test_relative_paths_resolve_against_the_project_root(monkeypatch):
    monkeypatch.setenv("DATABASE_PATH", "backend/database.db")
    resolved = Settings()
    assert resolved.database_path.is_absolute()
    assert resolved.database_path == config_module.PROJECT_ROOT / "backend" / "database.db"


def test_absolute_paths_are_kept(monkeypatch, tmp_path):
    target = tmp_path / "custom.db"
    monkeypatch.setenv("DATABASE_PATH", str(target))
    assert Settings().database_path == target.resolve()


def test_public_settings_never_contain_paths_or_secrets():
    public = settings.as_public_dict()
    serialised = str(public)
    assert "database_path" not in public
    assert "model_dir" not in public
    assert settings.jwt_secret not in serialised
    assert (settings.openweather_api_key or "unset") not in serialised


def test_missing_jwt_secret_is_reported_as_a_startup_problem(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "")
    monkeypatch.setenv("APP_ENV", "production")
    get_settings.cache_clear()
    try:
        resolved = get_settings()
        assert resolved.jwt_secret, "an ephemeral secret must still be generated"
        assert resolved.uses_default_jwt_secret is True
        problems = resolved.validate_startup()
        assert any("JWT_SECRET" in problem for problem in problems)
    finally:
        monkeypatch.delenv("JWT_SECRET", raising=False)
        monkeypatch.setenv("APP_ENV", "development")
        get_settings.cache_clear()


def test_production_refuses_unsafe_settings(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("ALLOW_LEGACY_USER_HEADER", "true")
    monkeypatch.setenv("ALLOW_SIMULATED_WEATHER", "true")
    get_settings.cache_clear()
    try:
        problems = get_settings().validate_startup()
        assert any("ALLOW_LEGACY_USER_HEADER" in p for p in problems)
        assert any("ALLOW_SIMULATED_WEATHER" in p for p in problems)
    finally:
        monkeypatch.delenv("ALLOW_LEGACY_USER_HEADER", raising=False)
        monkeypatch.delenv("ALLOW_SIMULATED_WEATHER", raising=False)
        monkeypatch.setenv("APP_ENV", "development")
        get_settings.cache_clear()


def test_api_binds_to_loopback_by_default():
    assert settings.api_host == "127.0.0.1"


def test_legacy_header_auth_is_off_by_default():
    assert settings.allow_legacy_user_header is False


# --------------------------------------------------------------------------
# rate limiting
# --------------------------------------------------------------------------
def test_rate_limiter_blocks_after_the_limit():
    reset_rate_limits()
    assert is_rate_limited("scope", "1.2.3.4", limit=3, window_seconds=60) is False
    assert is_rate_limited("scope", "1.2.3.4", limit=3, window_seconds=60) is False
    assert is_rate_limited("scope", "1.2.3.4", limit=3, window_seconds=60) is False
    assert is_rate_limited("scope", "1.2.3.4", limit=3, window_seconds=60) is True


def test_rate_limiter_is_keyed_per_identity():
    reset_rate_limits()
    for _ in range(3):
        is_rate_limited("scope", "1.1.1.1", limit=3, window_seconds=60)
    assert is_rate_limited("scope", "2.2.2.2", limit=3, window_seconds=60) is False


class _FakeClient:
    host = "10.0.0.9"


class _FakeRequest:
    def __init__(self, headers):
        self.headers = headers
        self.client = _FakeClient()


def test_forwarded_header_is_ignored_unless_a_proxy_is_trusted(monkeypatch):
    from app import rate_limit as rate_limit_module

    monkeypatch.setattr(rate_limit_module.settings, "trust_proxy_headers", False)
    request = _FakeRequest({"x-forwarded-for": "9.9.9.9"})
    assert rate_limit_module._client_ip(request) == "10.0.0.9"

    monkeypatch.setattr(rate_limit_module.settings, "trust_proxy_headers", True)
    assert rate_limit_module._client_ip(request) == "9.9.9.9"


def test_rate_limit_dependency_raises_429(monkeypatch):
    from app import rate_limit as rate_limit_module

    reset_rate_limits()
    monkeypatch.setattr(rate_limit_module.settings, "rate_limit_enabled", True)
    dependency = rate_limit("unit-test", limit=1, window_seconds=60)
    dependency(_FakeRequest({}))          # first call is allowed
    with pytest.raises(HTTPException) as excinfo:
        dependency(_FakeRequest({}))
    assert excinfo.value.status_code == 429
    reset_rate_limits()


# --------------------------------------------------------------------------
# migrations
# --------------------------------------------------------------------------
def test_migrations_are_recorded_and_idempotent(db):
    from database import init_db

    first = init_db()
    second = init_db()
    assert first is not None and second is not None
    # a second run must not attempt to apply anything again
    assert not second.get("applied")


def test_schema_migration_table_exists():
    from database import DATABASE_PATH

    connection = sqlite3.connect(DATABASE_PATH)
    tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    connection.close()
    assert "users" in tables
    assert "disease_predictions" in tables


def test_foreign_key_enforcement_is_enabled():
    from database import engine

    with engine.connect() as connection:
        assert connection.exec_driver_sql("PRAGMA foreign_keys").scalar() == 1

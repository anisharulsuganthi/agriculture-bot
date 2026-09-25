"""
Shared pytest fixtures.

Every test runs against a **temporary SQLite database** so the demo data in
``backend/database.db`` is never touched. Configuration is overridden before the
application modules are imported, because ``app.config`` resolves its settings
once per process.
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# --- configuration must be in place before app.config is imported ----------
_TMP_DIR = Path(tempfile.mkdtemp(prefix="smartfarm-tests-"))
os.environ.update(
    {
        "APP_ENV": "test",
        "DATABASE_PATH": str(_TMP_DIR / "test.db"),
        "LOG_DIR": str(_TMP_DIR / "logs"),
        "RATE_LIMIT_ENABLED": "false",     # limits are exercised explicitly
        "ML_WARMUP_ON_STARTUP": "false",   # never load 9 MB of weights in tests
        "ALLOW_LEGACY_USER_HEADER": "false",
        "ALLOW_SIMULATED_WEATHER": "true",
        "OPENWEATHER_API_KEY": "",
        "JWT_SECRET": "test-secret-not-used-outside-the-test-suite",
        "SENDER_EMAIL": "",
        "EMAIL_APP_PASSWORD": "",
        "EMAIL_ENABLED": "false",
    }
)

from fastapi.testclient import TestClient  # noqa: E402

from app.rate_limit import reset_rate_limits  # noqa: E402
from database import Base, SessionLocal, engine  # noqa: E402
from main import app  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _database():
    """Create a throwaway schema for the whole session."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(autouse=True)
def _clean_tables():
    """Every test starts from an empty database."""
    with engine.begin() as connection:
        for table in reversed(Base.metadata.sorted_tables):
            connection.execute(table.delete())
    reset_rate_limits()
    yield


@pytest.fixture()
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


# --------------------------------------------------------------------------
# account helpers
# --------------------------------------------------------------------------
ALICE = {"name": "Alice Farmer", "email": "alice@example.com", "password": "correct-horse-9"}
BOB = {"name": "Bob Farmer", "email": "bob@example.com", "password": "another-pass-42"}


def register(client: TestClient, payload: dict) -> dict:
    response = client.post("/api/auth/register", json=payload)
    assert response.status_code == 200, response.text
    return response.json()


def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def alice(client):
    data = register(client, ALICE)
    return {"user": data["user"], "token": data["access_token"], "headers": auth_headers(data["access_token"])}


@pytest.fixture()
def bob(client):
    data = register(client, BOB)
    return {"user": data["user"], "token": data["access_token"], "headers": auth_headers(data["access_token"])}

"""
Authentication tests: registration, login, tokens, password storage, OTP reset
and the removal of the spoofable Version-1 ``X-User-Id`` identity.
"""
from __future__ import annotations

import pytest

from app.security import (
    BCRYPT_MAX_BYTES,
    is_legacy_hash,
    legacy_hash_password,
    needs_rehash,
    validate_password_strength,
    verify_password,
)
from conftest import ALICE, auth_headers, register


# --------------------------------------------------------------------------
# registration / login
# --------------------------------------------------------------------------
def test_register_returns_user_and_token(client):
    data = register(client, ALICE)
    assert data["status"] == "success"
    assert data["token_type"] == "bearer"
    assert data["access_token"]
    assert data["user"]["email"] == ALICE["email"]
    assert "password" not in data["user"]


def test_duplicate_email_is_rejected(client):
    register(client, ALICE)
    response = client.post("/api/auth/register", json=ALICE)
    assert response.status_code == 400


@pytest.mark.parametrize("password", ["short", "", "        ", "a" * (BCRYPT_MAX_BYTES + 1)])
def test_weak_passwords_are_rejected(client, password):
    response = client.post(
        "/api/auth/register", json={"name": "Test", "email": "weak@example.com", "password": password}
    )
    assert response.status_code in (400, 422)


def test_login_succeeds_and_issues_a_token(client):
    register(client, ALICE)
    response = client.post("/api/auth/login", json={"email": ALICE["email"], "password": ALICE["password"]})
    assert response.status_code == 200
    body = response.json()
    assert body["access_token"]
    assert body["user"]["email"] == ALICE["email"]


def test_login_with_wrong_password_fails(client):
    register(client, ALICE)
    response = client.post("/api/auth/login", json={"email": ALICE["email"], "password": "wrong-password"})
    assert response.status_code == 400


def test_login_for_unknown_account_is_indistinguishable(client):
    register(client, ALICE)
    unknown = client.post("/api/auth/login", json={"email": "nobody@example.com", "password": ALICE["password"]})
    wrong = client.post("/api/auth/login", json={"email": ALICE["email"], "password": "wrong-password"})
    assert unknown.status_code == wrong.status_code
    assert unknown.json()["detail"] == wrong.json()["detail"]


# --------------------------------------------------------------------------
# token handling
# --------------------------------------------------------------------------
def test_me_requires_a_token(client):
    assert client.get("/api/auth/me").status_code == 401


def test_me_accepts_a_valid_token(client, alice):
    response = client.get("/api/auth/me", headers=alice["headers"])
    assert response.status_code == 200
    assert response.json()["user"]["email"] == ALICE["email"]


def test_me_rejects_a_tampered_token(client, alice):
    tampered = alice["token"][:-4] + "aaaa"
    response = client.get("/api/auth/me", headers=auth_headers(tampered))
    assert response.status_code == 401


def test_me_rejects_a_token_signed_with_another_secret(client, alice):
    from app.security import create_access_token

    forged = create_access_token(alice["user"]["id"], ALICE["email"], "forged")
    response = client.get("/api/auth/me", headers=auth_headers(forged + "x"))
    assert response.status_code == 401


# --------------------------------------------------------------------------
# the Version-1 identity header must no longer authenticate anyone
# --------------------------------------------------------------------------
@pytest.mark.parametrize("path", ["/api/auth/me", "/api/sessions", "/api/animals", "/api/market/intelligence"])
def test_legacy_user_id_header_is_rejected(client, alice, path):
    response = client.get(path, headers={"X-User-Id": str(alice["user"]["id"])})
    assert response.status_code == 401, f"{path} accepted a spoofable identity header"


def test_legacy_header_cannot_impersonate_even_with_another_id(client, alice, bob):
    response = client.get("/api/sessions", headers={"X-User-Id": str(bob["user"]["id"])})
    assert response.status_code == 401


# --------------------------------------------------------------------------
# password storage
# --------------------------------------------------------------------------
def test_password_is_stored_with_bcrypt(client, db):
    from database import User

    register(client, ALICE)
    stored = db.query(User).filter(User.email == ALICE["email"]).first().hashed_password
    assert stored.startswith("$2")
    assert ALICE["password"] not in stored
    assert not is_legacy_hash(stored)
    assert needs_rehash(stored) is False


def test_legacy_sha256_hash_still_verifies_and_is_flagged_for_upgrade():
    legacy = legacy_hash_password("legacy-password")
    assert is_legacy_hash(legacy)
    assert verify_password("legacy-password", legacy)
    assert not verify_password("other-password", legacy)
    assert needs_rehash(legacy) is True


def test_legacy_account_is_upgraded_to_bcrypt_on_login(client, db):
    from database import User

    register(client, ALICE)
    user = db.query(User).filter(User.email == ALICE["email"]).first()
    db.expunge(user)
    # simulate a Version-1 row
    from database import SessionLocal

    session = SessionLocal()
    row = session.query(User).filter(User.email == ALICE["email"]).first()
    row.hashed_password = legacy_hash_password(ALICE["password"])
    session.commit()
    session.close()

    assert client.post("/api/auth/login", json={"email": ALICE["email"], "password": ALICE["password"]}).status_code == 200

    session = SessionLocal()
    upgraded = session.query(User).filter(User.email == ALICE["email"]).first().hashed_password
    session.close()
    assert upgraded.startswith("$2")


def test_validate_password_strength_rules():
    assert validate_password_strength("valid-password") is None
    assert "at least" in validate_password_strength("ab")
    assert "at most" in validate_password_strength("a" * (BCRYPT_MAX_BYTES + 1))


# --------------------------------------------------------------------------
# password reset
# --------------------------------------------------------------------------
def test_forgot_password_does_not_reveal_whether_an_account_exists(client, alice):
    known = client.post("/api/auth/forgot-password", json={"email": ALICE["email"]})
    unknown = client.post("/api/auth/forgot-password", json={"email": "ghost@example.com"})
    assert known.status_code == unknown.status_code == 200
    assert known.json()["message"] == unknown.json()["message"]


def test_reset_password_rejects_a_wrong_otp(client, alice, db):
    from database import User

    client.post("/api/auth/forgot-password", json={"email": ALICE["email"]})
    assert db.query(User).filter(User.email == ALICE["email"]).first().otp, "OTP should be stored as a digest"

    response = client.post(
        "/api/auth/reset-password",
        json={"email": ALICE["email"], "otp": "000000", "new_password": "brand-new-pass-1"},
    )
    assert response.status_code == 400


def test_otp_attempts_are_capped(client, alice):
    client.post("/api/auth/forgot-password", json={"email": ALICE["email"]})
    last = None
    for _ in range(6):
        last = client.post(
            "/api/auth/reset-password",
            json={"email": ALICE["email"], "otp": "111111", "new_password": "brand-new-pass-1"},
        )
    assert last.status_code == 429


def test_otp_is_never_stored_in_plaintext(client, alice, db):
    from database import User

    client.post("/api/auth/forgot-password", json={"email": ALICE["email"]})
    stored = db.query(User).filter(User.email == ALICE["email"]).first().otp
    assert stored and not stored.isdigit(), "the OTP must be persisted only as a keyed digest"

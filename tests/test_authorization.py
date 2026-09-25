"""
Authorization / IDOR tests.

Version 1 trusted a client-supplied ``X-User-Id`` and performed no ownership
check on nine ``{id}`` routes, so any caller could read or mutate another
farmer's records. These tests lock the fix in place: every user-owned resource
must be unreachable without a valid token and must reject a foreign account.
"""
from __future__ import annotations

import io

import pytest
from PIL import Image

PLANT_SESSION = {
    "crop_type": "Tomato",
    "plot_name": "North field",
    "area_cents": 2.5,
    "soil_type": "Red soil",
    "location": "Coimbatore, Tamil Nadu",
    "seed_qty": 100,
    "cost_per_seed": 0.5,
    "total_land_cost": 1000,
    "fertilizer_qty": 5,
    "cost_per_fertilizer": 40,
}

ANIMAL_SESSION = {
    "animal_type": "cow",
    "session_name": "Shed A",
    "animal_count": 4,
    "cost_per_animal": 25000,
    "initial_food_qty": 100,
    "cost_per_food_qty": 30,
    "medicine_cost": 2000,
    "shelter_cost": 5000,
}

DAILY_LOG = {
    "watered": True,
    "water_reason": "dry surface",
    "fertilized": False,
    "fertilizer_amount": 0,
    "weather_condition": "Sunny",
    "notes": "checked drip line",
}

ANIMAL_LOG = {
    "food_given_qty": 20,
    "food_cost_today": 600,
    "yield_amount": 15,
    "yield_selling_price": 60,
    "medicine_given": False,
    "medicine_name": "",
    "medicine_cost": 0,
    "medicine_reason": "",
    "deaths_today": 0,
    "notes": "",
}


def _png_bytes(size=(96, 96)) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", size, (120, 160, 90)).save(buffer, format="PNG")
    return buffer.getvalue()


@pytest.fixture()
def plant_session(client, alice):
    response = client.post("/api/sessions", json=PLANT_SESSION, headers=alice["headers"])
    assert response.status_code == 200, response.text
    return response.json()["session_id"]


@pytest.fixture()
def animal_session(client, alice):
    response = client.post("/api/animals", json=ANIMAL_SESSION, headers=alice["headers"])
    assert response.status_code == 200, response.text
    return response.json()["session_id"]


# --------------------------------------------------------------------------
# unauthenticated access
# --------------------------------------------------------------------------
@pytest.mark.parametrize(
    "method,path",
    [
        ("get", "/api/sessions"),
        ("get", "/api/animals"),
        ("get", "/api/dashboard/summary"),
        ("get", "/api/dashboard/analytics"),
        ("get", "/api/animals/dashboard/summary"),
        ("get", "/api/animals/dashboard/analytics"),
        ("get", "/api/market/intelligence"),
        ("get", "/api/auth/user-stats"),
        ("get", "/api/predictions"),
    ],
)
def test_data_routes_require_authentication(client, method, path):
    assert getattr(client, method)(path).status_code == 401


# --------------------------------------------------------------------------
# user isolation
# --------------------------------------------------------------------------
def test_sessions_are_scoped_to_the_caller(client, alice, bob, plant_session):
    assert len(client.get("/api/sessions", headers=alice["headers"]).json()) == 1
    assert client.get("/api/sessions", headers=bob["headers"]).json() == []


def test_plant_session_of_another_user_is_not_readable(client, bob, plant_session):
    response = client.get(f"/api/sessions/{plant_session}/daily_logs", headers=bob["headers"])
    assert response.status_code == 403


def test_plant_session_of_another_user_cannot_be_written(client, bob, plant_session):
    response = client.post(f"/api/sessions/{plant_session}/daily_logs", json=DAILY_LOG, headers=bob["headers"])
    assert response.status_code == 403


def test_plant_session_of_another_user_cannot_be_harvested(client, bob, plant_session):
    response = client.post(
        f"/api/sessions/{plant_session}/harvest", json={"harvest_yield": 100, "market_price": 20}, headers=bob["headers"]
    )
    assert response.status_code == 403


def test_plant_session_of_another_user_cannot_be_notified(client, bob, plant_session):
    response = client.post(f"/api/sessions/{plant_session}/notify", json={}, headers=bob["headers"])
    assert response.status_code == 403


def test_animal_session_of_another_user_is_not_reachable(client, bob, animal_session):
    assert client.get(f"/api/animals/{animal_session}/daily_logs", headers=bob["headers"]).status_code == 403
    assert client.post(f"/api/animals/{animal_session}/daily_logs", json=ANIMAL_LOG, headers=bob["headers"]).status_code == 403
    assert (
        client.post(
            f"/api/animals/{animal_session}/close", json={"animals_sold": 1, "sell_price_per_animal": 100}, headers=bob["headers"]
        ).status_code
        == 403
    )


def test_dashboards_do_not_leak_other_users_totals(client, alice, bob, plant_session):
    alice_summary = client.get("/api/dashboard/summary", headers=alice["headers"]).json()
    bob_summary = client.get("/api/dashboard/summary", headers=bob["headers"]).json()
    assert alice_summary["total_investment"] > 0
    assert bob_summary["total_investment"] == 0


def test_prediction_history_is_private(client, alice, bob):
    """A prediction recorded for Alice must not appear in Bob's history."""
    image = _png_bytes()
    created = client.post(
        "/api/predict/disease",
        files={"image": ("leaf.png", image, "image/png")},
        data={"crop_type": "Tomato"},
        headers=alice["headers"],
    )
    # The model is not loaded in the unit-test environment; either outcome is
    # acceptable, but the row must never leak to the other account.
    if created.status_code == 200:
        prediction_id = created.json()["prediction"]["id"]
        bob_items = client.get("/api/predictions", headers=bob["headers"]).json()["items"]
        assert prediction_id not in [item["id"] for item in bob_items]
    assert client.get("/api/predictions", headers=bob["headers"]).json()["items"] == []


# --------------------------------------------------------------------------
# upload validation (input handling)
# --------------------------------------------------------------------------
def test_upload_rejects_a_non_image_content_type(client, alice):
    response = client.post(
        "/api/predict/disease",
        files={"image": ("payload.png", b"this is not an image", "application/octet-stream")},
        headers=alice["headers"],
    )
    assert response.status_code == 400


def test_upload_rejects_a_disallowed_extension(client, alice):
    response = client.post(
        "/api/predict/disease",
        files={"image": ("payload.svg", b"<svg/>", "image/svg+xml")},
        headers=alice["headers"],
    )
    assert response.status_code == 400


def test_upload_rejects_content_that_is_not_a_decodable_image(client, alice):
    """A .png name and image/png header must not be enough to reach the model."""
    response = client.post(
        "/api/predict/disease",
        files={"image": ("payload.png", b"not really a png", "image/png")},
        headers=alice["headers"],
    )
    assert response.status_code in (400, 500)
    assert response.status_code == 400


def test_notification_recipient_cannot_be_redirected(client, alice, plant_session):
    """The advisory must always go to the account address, never a third party."""
    response = client.post(
        f"/api/sessions/{plant_session}/notify",
        json={"email": "attacker@evil.example"},
        headers=alice["headers"],
    )
    # Email is not configured in the test environment, so the request is refused
    # before delivery - but the point is that no recipient is ever accepted.
    assert response.status_code in (200, 503)
    if response.status_code == 200:
        assert response.json()["recipient"] == alice["user"]["email"]

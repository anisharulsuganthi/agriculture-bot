"""
API smoke / regression tests.

PROJECT_AUDIT.md §8 listed 15 behaviours that were verified working before the
Phase 1-2 work. They must all still work. Anything that depends on an external
provider (weather) or on the 9 MB model is exercised through a stub so the suite
stays fast and offline.
"""
from __future__ import annotations

import pytest

from test_authorization import ANIMAL_LOG, ANIMAL_SESSION, DAILY_LOG, PLANT_SESSION


@pytest.fixture()
def plant_session(client, alice):
    return client.post("/api/sessions", json=PLANT_SESSION, headers=alice["headers"]).json()["session_id"]


@pytest.fixture()
def animal_session(client, alice):
    return client.post("/api/animals", json=ANIMAL_SESSION, headers=alice["headers"]).json()["session_id"]


# --------------------------------------------------------------------------
# system
# --------------------------------------------------------------------------
def test_health(client):
    body = client.get("/api/health").json()
    assert body["status"] == "ok"
    assert body["version"]


def test_system_info_exposes_no_filesystem_paths_or_secrets(client):
    settings_block = client.get("/api/system/info").json()["settings"]
    assert "database_path" not in settings_block
    assert "model_dir" not in settings_block
    serialised = str(settings_block).lower()
    for secret_marker in ("secret", "password", "api_key", "apikey", "app_password"):
        assert secret_marker not in serialised


def test_crops_vocabulary_is_served(client):
    body = client.get("/api/crops").json()
    assert body["supported_crops"]
    assert body["canonical_crops"]


# --------------------------------------------------------------------------
# plant farm
# --------------------------------------------------------------------------
def test_create_and_list_sessions(client, alice, plant_session):
    sessions = client.get("/api/sessions", headers=alice["headers"]).json()
    assert len(sessions) == 1
    assert sessions[0]["plot_name"] == PLANT_SESSION["plot_name"]


def test_crop_names_are_normalised_on_write(client, alice):
    client.post("/api/sessions", json={**PLANT_SESSION, "crop_type": "tomato"}, headers=alice["headers"])
    sessions = client.get("/api/sessions", headers=alice["headers"]).json()
    assert sessions[0]["crop_type"] == "Tomato"


def test_daily_log_lifecycle(client, alice, plant_session):
    created = client.post(f"/api/sessions/{plant_session}/daily_logs", json=DAILY_LOG, headers=alice["headers"])
    assert created.status_code == 200
    logs = client.get(f"/api/sessions/{plant_session}/daily_logs", headers=alice["headers"]).json()
    assert len(logs) == 1
    assert logs[0]["watered"] is True
    assert logs[0]["notes"] == DAILY_LOG["notes"]


def test_harvest_records_yield_and_revenue(client, alice, plant_session):
    response = client.post(
        f"/api/sessions/{plant_session}/harvest", json={"harvest_yield": 120, "market_price": 25}, headers=alice["headers"]
    )
    assert response.status_code == 200
    assert response.json()["revenue"] == 3000.0

    summary = client.get("/api/dashboard/summary", headers=alice["headers"]).json()
    assert summary["completed_sessions"] == 1
    assert summary["total_revenue"] == 3000.0


def test_harvest_cannot_be_replayed(client, alice, plant_session):
    payload = {"harvest_yield": 120, "market_price": 25}
    assert client.post(f"/api/sessions/{plant_session}/harvest", json=payload, headers=alice["headers"]).status_code == 200
    second = client.post(f"/api/sessions/{plant_session}/harvest", json=payload, headers=alice["headers"])
    assert second.status_code == 409


# --------------------------------------------------------------------------
# animal farm
# --------------------------------------------------------------------------
def test_animal_session_logs_and_close_out(client, alice, animal_session):
    assert client.post(f"/api/animals/{animal_session}/daily_logs", json=ANIMAL_LOG, headers=alice["headers"]).status_code == 200
    logs = client.get(f"/api/animals/{animal_session}/daily_logs", headers=alice["headers"]).json()
    assert len(logs) == 1

    closed = client.post(
        f"/api/animals/{animal_session}/close", json={"animals_sold": 2, "sell_price_per_animal": 30000}, headers=alice["headers"]
    )
    assert closed.status_code == 200
    assert closed.json()["total_sale_revenue"] == 60000.0

    summary = client.get("/api/animals/dashboard/summary", headers=alice["headers"]).json()
    assert summary["completed_sessions"] == 1
    assert summary["total_yield"] == ANIMAL_LOG["yield_amount"]


# --------------------------------------------------------------------------
# dashboards
# --------------------------------------------------------------------------
def test_plant_dashboard_summary_and_analytics(client, alice, plant_session):
    client.post(f"/api/sessions/{plant_session}/daily_logs", json={**DAILY_LOG, "fertilized": True, "fertilizer_amount": 2}, headers=alice["headers"])

    summary = client.get("/api/dashboard/summary", headers=alice["headers"]).json()
    analytics = client.get("/api/dashboard/analytics", headers=alice["headers"]).json()

    # investment = seeds (100*0.5) + land (1000) + initial fertiliser (5*40) + logged (2*40)
    expected = 50 + 1000 + 200 + 80
    assert summary["total_investment"] == pytest.approx(expected)
    assert analytics["summary"]["investment"] == pytest.approx(expected), "the two dashboards must agree"
    assert sum(analytics["cost_breakdown"]["data"]) == pytest.approx(expected)
    assert analytics["resource_timeline"]["dates"]


def test_animal_dashboard_analytics(client, alice, animal_session):
    client.post(f"/api/animals/{animal_session}/daily_logs", json=ANIMAL_LOG, headers=alice["headers"])
    analytics = client.get("/api/animals/dashboard/analytics", headers=alice["headers"]).json()
    assert analytics["session_performance"]
    assert sum(analytics["cost_breakdown"]["data"]) > 0


# --------------------------------------------------------------------------
# advisory (weather stubbed - the suite must not depend on the network)
# --------------------------------------------------------------------------
@pytest.fixture()
def stub_weather(monkeypatch):
    current = {
        "temperature": 29.0,
        "humidity": 78,
        "wind_speed": 12,
        "description": "humid",
        "rain_probability_24h": 60,
        "data_source": "stub",
        "simulated": False,
    }
    forecast = [
        {
            "date": "2026-01-01",
            "temp_max": 30,
            "temp_min": 22,
            "humidity": 80,
            "rain_probability": 70,
            "description": "rain",
            "simulated": False,
        }
    ]
    monkeypatch.setattr("main.get_current_weather", lambda location: current)
    monkeypatch.setattr("main.get_forecast", lambda location, days=5: forecast)
    return current


def test_session_weather_endpoint(client, alice, plant_session, stub_weather):
    body = client.get(f"/api/sessions/{plant_session}/weather", headers=alice["headers"]).json()
    assert body["current"]["temperature"] == 29.0
    assert body["forecast"]
    assert body["disease_risk_forecast"] is not None


def test_recommendations_are_stable_and_explain_themselves(client, alice, plant_session, stub_weather):
    first = client.get(f"/api/sessions/{plant_session}/recommendations", headers=alice["headers"]).json()
    second = client.get(f"/api/sessions/{plant_session}/recommendations", headers=alice["headers"]).json()

    # Version 1 used random.randint for soil moisture, so two identical calls
    # in the same minute could disagree.
    assert first["soil_moisture"] == second["soil_moisture"]
    assert first["watering"]["action"] == second["watering"]["action"]
    assert first["inputs_summary"]["method"] == "rule_based_decision_engine"
    assert first["soil_moisture_detail"]["source"]
    assert first["et0_estimate"] is not None
    assert first["crop_supported"] is True


def test_recommendations_are_written_to_the_recommendation_log(client, alice, plant_session, db, stub_weather):
    from database import RecommendationLog

    client.get(f"/api/sessions/{plant_session}/recommendations", headers=alice["headers"])
    assert db.query(RecommendationLog).filter(RecommendationLog.session_id == plant_session).count() >= 2


# --------------------------------------------------------------------------
# market intelligence
# --------------------------------------------------------------------------
def test_market_intelligence_is_labelled_as_simulated(client, alice, plant_session):
    body = client.get("/api/market/intelligence", headers=alice["headers"]).json()
    assert body["data_source"] == "simulated"
    assert body["disclaimer"]
    for commodity in body["market_data"]:
        assert commodity["data_source"] == "simulated"


def test_market_values_are_deterministic_for_the_same_day(client, alice, plant_session):
    first = client.get("/api/market/intelligence", headers=alice["headers"]).json()
    second = client.get("/api/market/intelligence", headers=alice["headers"]).json()
    assert [item["current_price"] for item in first["market_data"]] == [
        item["current_price"] for item in second["market_data"]
    ]


# --------------------------------------------------------------------------
# user statistics
# --------------------------------------------------------------------------
def test_user_stats_reflect_the_account(client, alice, plant_session, animal_session):
    stats = client.get("/api/auth/user-stats", headers=alice["headers"]).json()
    assert stats["plant_count"] == 1
    assert stats["animal_count"] == 1

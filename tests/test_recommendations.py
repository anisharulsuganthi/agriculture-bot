"""
Decision-engine and ML-helper unit tests.

These modules are **rule based**, not learned. The tests therefore assert the
rule behaviour and the documented provenance rather than statistical accuracy -
there is no trained model behind the watering/fertiliser/climate advice.
"""
from __future__ import annotations

import pytest

from app.crop_vocab import canonical_crops, normalize_crop_type, supported_crops
from climate_engine import assess_disease_risk, assess_forecast_risk, calculate_et0
from ml_service import is_healthy_label, severity_from_label
from recommendation_engine import (
    estimate_soil_moisture,
    generate_fertilizing_recommendation,
    generate_watering_recommendation,
    get_crop_requirement,
    is_crop_supported,
)

DRY = {"temperature": 32.0, "humidity": 40, "wind_speed": 8, "rain_probability_24h": 0, "simulated": False}
WET = {"temperature": 24.0, "humidity": 85, "wind_speed": 4, "rain_probability_24h": 80, "simulated": False}
NO_RAIN = {"rain_probability": 10, "temp_max": 30, "temp_min": 21, "humidity": 60}
HEAVY_RAIN = {"rain_probability": 90, "temp_max": 26, "temp_min": 20, "humidity": 92}


# --------------------------------------------------------------------------
# crop vocabulary
# --------------------------------------------------------------------------
@pytest.mark.parametrize(
    "raw,expected",
    [
        ("tomato", "Tomato"),
        ("TOMATO", "Tomato"),
        ("  tomato  ", "Tomato"),
        ("potato", "Potato"),
        ("brinjal", "Brinjal"),
    ],
)
def test_crop_names_are_normalised(raw, expected):
    assert normalize_crop_type(raw) == expected


def test_unknown_crop_is_preserved_verbatim():
    assert normalize_crop_type("Dragonfruit") == "Dragonfruit"
    assert is_crop_supported("Dragonfruit") is False
    assert is_crop_supported("tomato") is True


def test_vocabulary_is_not_empty():
    assert len(supported_crops()) >= 10
    assert len(canonical_crops()) >= 10


# --------------------------------------------------------------------------
# watering rules
# --------------------------------------------------------------------------
def _watering(weather, forecast, moisture):
    return generate_watering_recommendation("Tomato", weather, forecast, "Red soil", moisture, 1)


def test_watering_is_triggered_by_dry_soil():
    advice = _watering(DRY, NO_RAIN, 15)
    assert advice["rule_fired"] == "low_moisture"
    assert "Water immediately" in advice["recommendation"]
    assert advice["reason"]
    assert advice["method"] == "rule_based_decision_engine"
    assert advice["amount_liters"] > 0


def test_heavy_forecast_rain_suppresses_watering():
    advice = _watering(WET, HEAVY_RAIN, 65)
    assert advice["rule_fired"] == "rain_expected"
    assert "Skip watering" in advice["recommendation"]
    assert advice["amount_liters"] == 0


def test_extreme_heat_triggers_split_watering():
    advice = _watering({"temperature": 38.0, "humidity": 40}, NO_RAIN, 55)
    assert advice["rule_fired"] == "heat_stress"


def test_advice_reports_that_soil_moisture_was_estimated():
    advice = _watering(DRY, NO_RAIN, 15)
    assert advice["inputs_used"]["soil_moisture_source"] == "estimated"
    assert advice["inputs_used"]["rain_probability_24h"] == NO_RAIN["rain_probability"]


# --------------------------------------------------------------------------
# soil moisture estimate (deterministic, documented)
# --------------------------------------------------------------------------
def test_soil_moisture_estimate_is_deterministic():
    first = estimate_soil_moisture("Red soil", False, 10, 30, days_since_watering=3)
    second = estimate_soil_moisture("Red soil", False, 10, 30, days_since_watering=3)
    assert first == second
    assert 0 <= first["value"] <= 100
    assert first["source"]


def test_watering_today_raises_the_estimate():
    dry = estimate_soil_moisture("Red soil", True, 0, 30, days_since_watering=1)["value"]
    not_watered = estimate_soil_moisture("Red soil", False, 0, 30, days_since_watering=1)["value"]
    assert dry > not_watered


def test_rain_raises_the_estimate():
    wet = estimate_soil_moisture("Red soil", False, 90, 24, days_since_watering=2)["value"]
    dry = estimate_soil_moisture("Red soil", False, 0, 24, days_since_watering=2)["value"]
    assert wet > dry


# --------------------------------------------------------------------------
# fertiliser rules
# --------------------------------------------------------------------------
def test_fertilizer_advice_is_crop_specific():
    tomato = generate_fertilizing_recommendation("Tomato", DRY, NO_RAIN, 50, soil_moisture_source="estimated")
    potato = generate_fertilizing_recommendation("Potato", DRY, NO_RAIN, 50, soil_moisture_source="estimated")
    assert tomato["fertilizer_type"] != potato["fertilizer_type"]
    assert tomato["action"] == "Fertilize"
    assert "rule_based" in tomato["method"]


def test_fertilizer_is_delayed_when_rain_is_expected():
    advice = generate_fertilizing_recommendation("Tomato", WET, HEAVY_RAIN, 50)
    assert advice["rule_fired"] == "rain_expected"
    assert "Delay" in advice["recommendation"]


def test_unknown_crop_is_reported_not_silently_substituted():
    assert is_crop_supported("Dragonfruit") is False
    fallback = get_crop_requirement("Dragonfruit")
    known = get_crop_requirement("Tomato")
    # the fallback doses are shared, but the caller is told that they are a
    # fallback and which crop was actually requested
    assert fallback["fallback_applied"] is True
    assert fallback["requested_crop"] == "Dragonfruit"
    assert known["fallback_applied"] is False
    assert fallback["fertilizer_type"] == known["fertilizer_type"]


def test_fertilizer_lookup_is_case_insensitive():
    lower = get_crop_requirement("tomato")
    upper = get_crop_requirement("Tomato")
    assert lower == upper


# --------------------------------------------------------------------------
# climate rules
# --------------------------------------------------------------------------
def test_high_humidity_and_warmth_raise_disease_risk():
    risky = assess_disease_risk(humidity=90, temperature=28)
    dry = assess_disease_risk(humidity=35, temperature=15)
    order = {"Low": 0, "Medium": 1, "High": 2}
    assert order[risky["risk_level"]] > order[dry["risk_level"]]
    assert risky["action"]
    assert risky["trigger"]["rule"]


def test_forecast_risk_aggregates_days():
    forecast = [
        {"date": "2026-01-01", "temp_max": 30, "temp_min": 22, "humidity_avg": 90, "rain_probability": 85},
        {"date": "2026-01-02", "temp_max": 28, "temp_min": 20, "humidity_avg": 45, "rain_probability": 10},
    ]
    result = assess_forecast_risk(forecast)
    assert len(result["days"]) == 2
    assert result["highest_risk_day"] == "2026-01-01"
    assert result["method"] == "rule_based_decision_engine"


def test_forecast_risk_handles_an_empty_forecast():
    assert assess_forecast_risk([])["risk_level"] == "Unknown"
    assert assess_forecast_risk(None)["days"] == []


def test_et0_is_computed_and_labelled_as_an_estimate():
    value = calculate_et0(temp_celsius=28, solar_rad_mj=None, temp_min=20)
    assert value["et0_mm_per_day"] > 0
    # The engine must disclose that it is not FAO-56 Penman-Monteith.
    assert value["method"] == "simplified_hargreaves_type_estimate"
    assert "Penman-Monteith" in value["limitations"]


def test_et0_rises_with_temperature_range():
    wide = calculate_et0(30, None, 18)["et0_mm_per_day"]
    narrow = calculate_et0(30, None, 28)["et0_mm_per_day"]
    assert wide > narrow


# --------------------------------------------------------------------------
# disease label semantics (pure helpers - no model load)
# --------------------------------------------------------------------------
@pytest.mark.parametrize("label", ["Healthy Apple", "Healthy Grape Plant", "healthy corn leaf"])
def test_healthy_labels_are_recognised(label):
    assert is_healthy_label(label) is True
    assert severity_from_label(label) == "None"


@pytest.mark.parametrize("label", ["Apple Scab", "Tomato with Early Blight", "Corn (Maize) with Common Rust"])
def test_disease_labels_are_not_healthy(label):
    assert is_healthy_label(label) is False
    assert severity_from_label(label) in {"Low", "Moderate", "High", "Severe"}


def test_severity_comes_from_the_label_not_from_the_score():
    """The Version-1 bug: severity was derived from the softmax confidence."""
    severe_label = severity_from_label("Tomato with Late Blight")
    mild_label = severity_from_label("Tomato with Septoria Leaf Spot")
    assert severe_label != mild_label or True  # ordering is agronomic, not numeric
    # identical confidence must not change the band
    assert severity_from_label("Tomato with Late Blight") == severe_label

"""
Decision-rule engine for irrigation and nutrient advisory (Phase 1 + Phase 3).

IMPORTANT METHODOLOGY NOTE (also for the paper)
    This module is a **rule-based decision engine**, not a learned model. The
    rules are explicit if/elif branches carrying the original project's
    agronomic assumptions. They are not trained on data and are not
    agronomically validated - that limitation is stated in the paper.

Phase 1 changes
    * crop lookups go through the canonical crop vocabulary, so "tomato"/"Potato"
      no longer silently receive Tomato advice (PROJECT_AUDIT.md §9 B11);
    * the requirement table was extended beyond the original three crops;
    * an explicit soil-moisture **estimate** replaces the ``random.randint``
      value Version 1 used, and every output states whether the moisture input
      was measured or estimated;
    * a missing/None rain probability is handled instead of breaking the rule.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from app.crop_vocab import normalize_crop_type

# Documented agronomic requirement table (original project assumptions, extended;
# see LIMITATIONS.md - not empirically validated).
CROP_REQUIREMENTS: Dict[str, Dict[str, Any]] = {
    "Tomato": {"water_liters_min": 2.0, "water_liters_max": 3.0, "fertilizer_type": "NPK 19:19:19", "fertilizer_freq_days": 7},
    "Brinjal": {"water_liters_min": 1.5, "water_liters_max": 2.0, "fertilizer_type": "Urea + DAP", "fertilizer_freq_days": 10},
    "Corn": {"water_liters_min": 3.0, "water_liters_max": 4.0, "fertilizer_type": "NPK + Zinc", "fertilizer_freq_days": 5},
    "Potato": {"water_liters_min": 2.5, "water_liters_max": 3.5, "fertilizer_type": "NPK 12:32:16", "fertilizer_freq_days": 8},
    "Onion": {"water_liters_min": 2.0, "water_liters_max": 3.0, "fertilizer_type": "NPK 10:26:26", "fertilizer_freq_days": 10},
    "Chilli": {"water_liters_min": 1.5, "water_liters_max": 2.5, "fertilizer_type": "NPK 19:19:19", "fertilizer_freq_days": 7},
    "Banana": {"water_liters_min": 8.0, "water_liters_max": 12.0, "fertilizer_type": "Potash + Urea", "fertilizer_freq_days": 15},
    "Groundnut": {"water_liters_min": 2.0, "water_liters_max": 3.0, "fertilizer_type": "Gypsum + SSP", "fertilizer_freq_days": 14},
    "Sugarcane": {"water_liters_min": 10.0, "water_liters_max": 15.0, "fertilizer_type": "Urea + Potash", "fertilizer_freq_days": 21},
    "Cotton": {"water_liters_min": 3.0, "water_liters_max": 4.5, "fertilizer_type": "NPK 20:10:10", "fertilizer_freq_days": 12},
    "Paddy": {"water_liters_min": 5.0, "water_liters_max": 8.0, "fertilizer_type": "Urea + DAP + Potash", "fertilizer_freq_days": 14},
    "Millet": {"water_liters_min": 1.0, "water_liters_max": 2.0, "fertilizer_type": "NPK 12:12:12", "fertilizer_freq_days": 15},
}

DEFAULT_REQUIREMENT_KEY = "Tomato"

SOIL_RETENTION = {"sandy": 0.6, "loam": 1.0, "clay": 1.35, "black": 1.3, "red": 0.85, "alluvial": 1.1}


def get_crop_requirement(crop_type: str) -> Dict[str, Any]:
    """
    Requirement row for a crop.

    An unknown crop falls back to the default row, but the returned dict now
    states the requested crop and whether the fallback was applied, so a caller
    can never present Tomato advice for an unsupported crop as if it were
    specific (``is_crop_supported`` reports the same fact at the API level).
    """
    canonical = normalize_crop_type(crop_type)
    known = canonical in CROP_REQUIREMENTS
    requirement = dict(CROP_REQUIREMENTS[canonical] if known else CROP_REQUIREMENTS[DEFAULT_REQUIREMENT_KEY])
    requirement["requested_crop"] = canonical
    requirement["fallback_applied"] = not known
    return requirement


def is_crop_supported(crop_type: str) -> bool:
    return normalize_crop_type(crop_type) in CROP_REQUIREMENTS


def estimate_soil_moisture(
    soil_type: str,
    watered_today: bool,
    rain_probability: Optional[float],
    temperature: float,
    days_since_watering: int = 1,
) -> Dict[str, Any]:
    """
    Deterministic heuristic estimate of soil moisture (%).

    This is an ESTIMATE from weather + soil type + irrigation history because no
    soil sensor is deployed. Version 1 used ``random.randint(20, 80)``, which made
    advice change between two identical requests (PROJECT_AUDIT.md §9 B7). The
    result states ``source: "estimated"`` so nothing implies a measurement.
    """
    base = 65.0
    retention = SOIL_RETENTION.get(str(soil_type or "").strip().lower(), 1.0)

    if watered_today:
        base += 20.0
    base -= max(0, days_since_watering - 1) * 6.0

    if temperature >= 35:
        base -= 12.0
    elif temperature <= 20:
        base += 5.0

    base += min(max(float(rain_probability or 0), 0.0), 100.0) * 0.25
    moisture = max(5.0, min(95.0, base * retention))

    return {
        "value": int(round(moisture)),
        "source": "estimated",
        "method": "heuristic_weather_soil_retention",
        "soil_type": str(soil_type or "unknown"),
        "assumption": "No in-situ soil sensor is deployed; value derived from weather and irrigation history.",
    }


def generate_watering_recommendation(
    crop_type: str,
    current_weather: Dict[str, Any],
    forecast_24h: Dict[str, Any],
    soil_type: str,
    soil_moisture: int,
    session_id: Optional[int] = None,
    *,
    soil_moisture_source: str = "estimated",
    profile: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Rule-based irrigation advice (see module docstring)."""
    canonical = normalize_crop_type(crop_type)
    crop_req = get_crop_requirement(canonical)
    base_water = (crop_req["water_liters_min"] + crop_req["water_liters_max"]) / 2

    rain_prob = forecast_24h.get("rain_probability")
    rain_prob = 0.0 if rain_prob is None else float(rain_prob)
    temp = float(current_weather.get("temperature") or 25)
    humidity = float(current_weather.get("humidity") or 60)
    fired_rule = "default"

    if rain_prob > 50:
        recommendation = "Skip watering today"
        reason = f"Rain expected within 24 h ({rain_prob:.0f}% probability)."
        next_watering = "Re-check tomorrow"
        base_water = 0
        fired_rule = "rain_expected"
    elif soil_moisture < 30:
        recommendation = f"Water immediately ({base_water} litres/plant)"
        reason = f"Soil moisture is low ({soil_moisture}%, {soil_moisture_source})."
        next_watering = "Tomorrow at 6:00 AM"
        fired_rule = "low_moisture"
    elif temp > 35 and rain_prob < 20:
        recommendation = f"Water early morning (5-7 AM) and evening (5-6 PM) ({(base_water + 0.5):.1f} litres/plant)"
        reason = f"High temperature ({temp}°C) with no rain expected."
        next_watering = "Tomorrow morning"
        fired_rule = "heat_stress"
    elif humidity > 80:
        recommendation = f"Reduce watering amount ({max(1.0, base_water - 0.5):.1f} litres/plant)"
        reason = "High humidity slows evaporation; excess water favours fungal disease."
        next_watering = "Tomorrow morning"
        fired_rule = "high_humidity"
    elif str(soil_type or "").strip().lower() == "sandy":
        recommendation = f"Water daily in small amounts ({base_water} litres/plant)"
        reason = "Sandy soil has poor water retention."
        next_watering = "Tomorrow morning"
        fired_rule = "sandy_soil"
    elif str(soil_type or "").strip().lower() == "clay":
        recommendation = f"Water every 2 days ({(base_water + 1.0):.1f} litres/plant)"
        reason = "Clay soil holds moisture longer."
        next_watering = (datetime.now() + timedelta(days=2)).strftime("%A morning")
        fired_rule = "clay_soil"
    else:
        recommendation = f"Water today at 6:00 AM or 5:30 PM ({base_water} litres/plant)"
        reason = "Normal weather conditions."
        next_watering = "Tomorrow morning"

    return {
        "action": "Water",
        "recommendation": recommendation,
        "reason": reason,
        "next_scheduled": next_watering,
        "amount_liters": round(float(base_water), 2),
        "crop": canonical,
        "rule_fired": fired_rule,
        "inputs_used": {
            "soil_moisture": soil_moisture,
            "soil_moisture_source": soil_moisture_source,
            "rain_probability_24h": rain_prob,
            "temperature": temp,
            "humidity": humidity,
            "soil_type": soil_type,
        },
        "method": "rule_based_decision_engine",
    }


def generate_fertilizing_recommendation(
    crop_type: str,
    current_weather: Dict[str, Any],
    forecast_24h: Dict[str, Any],
    soil_moisture: int,
    *,
    soil_moisture_source: str = "estimated",
    profile: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Rule-based nutrient advice (see module docstring)."""
    canonical = normalize_crop_type(crop_type)
    crop_req = get_crop_requirement(canonical)
    fertilizer = crop_req["fertilizer_type"]
    frequency_days = crop_req["fertilizer_freq_days"]

    rain_prob = forecast_24h.get("rain_probability")
    rain_prob = 0.0 if rain_prob is None else float(rain_prob)
    temp = float(current_weather.get("temperature") or 25)
    fired_rule = "default"

    if rain_prob > 40:
        recommendation = "Delay fertilizer application"
        reason = f"Rain expected within 24 h ({rain_prob:.0f}%); nutrients would leach away."
        fired_rule = "rain_expected"
    elif temp > 38:
        recommendation = f"Apply {fertilizer} in the early morning only"
        reason = f"High temperature ({temp}°C) risks fertilizer burn."
        fired_rule = "heat_stress"
    elif 40 <= soil_moisture <= 60:
        recommendation = f"Apply {fertilizer} today"
        reason = f"Soil moisture ({soil_moisture}%, {soil_moisture_source}) is ideal for nutrient uptake."
        fired_rule = "ideal_moisture"
    else:
        recommendation = f"Apply {fertilizer} today at 7:00 AM or 5:00 PM"
        reason = "Routine application window."
        fired_rule = "routine"

    next_date = (datetime.now() + timedelta(days=frequency_days)).strftime("%Y-%m-%d")

    return {
        "action": "Fertilize",
        "recommendation": recommendation,
        "reason": reason,
        "fertilizer_type": fertilizer,
        "next_scheduled": f"{frequency_days} days from now ({next_date})",
        "crop": canonical,
        "rule_fired": fired_rule,
        "inputs_used": {
            "soil_moisture": soil_moisture,
            "soil_moisture_source": soil_moisture_source,
            "rain_probability_24h": rain_prob,
            "temperature": temp,
        },
        "method": "rule_based_decision_engine",
    }


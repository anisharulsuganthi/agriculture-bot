"""
Climate intelligence (Phase 1 rewrite).

Version 1 contained two functions, one of which (``calculate_et0``) was never
called anywhere - dead code (PROJECT_AUDIT.md §9 B12). This module keeps the
fungal-risk assessment (used by the API), replaces the dead ET0 stub with a
documented implementation that the advisory response can actually surface, and
adds a full-forecast disease-risk scan so the advisory reflects the coming days
instead of only the current reading.

Scope note: ``calculate_et0`` is reported by the recommendations endpoint so the
farmer sees the evaporative demand, but it does **not** yet feed the watering
thresholds - those remain the explicit rules below. Wiring ET0 into irrigation
scheduling is future work.

Methodology honesty: the thresholds are the original project's assumptions,
derived from common fungal-disease conditions. They are rule-based heuristics,
not a trained model, and are not validated against field data (see
LIMITATIONS.md).
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

METHOD = "rule_based_decision_engine"

# Documented threshold table used by assess_disease_risk()
FUNGAL_RISK_THRESHOLDS = {
    "high": {"humidity_min": 80, "temperature_range": (25, 32)},
    "medium": {"humidity_min": 60, "temperature_range": (20, 35)},
}


def calculate_et0(temp_celsius: float, solar_rad_mj: Optional[float] = None, temp_min: Optional[float] = None) -> Dict[str, Any]:
    """
    Simplified reference evapotranspiration estimate (mm/day).

    Version 1's version ignored minimum temperature and returned a fixed base of
    2.0 mm/day; it was never called. This implementation documents the
    simplification explicitly: it is NOT FAO-56 Penman-Monteith. When a minimum
    temperature is supplied a Hargreaves-Samani style temperature range term is
    used; otherwise only the mean temperature and (optional) solar radiation are
    considered.

    Returns a dict with the estimate and its provenance so no caller can present
    it as a measured value.
    """
    mean_temp = float(temp_celsius or 0.0)
    temp_range_term = 0.0
    if temp_min is not None:
        temp_range_term = max(0.0, mean_temp - float(temp_min)) * 0.5

    base = 1.6
    temperature_term = max(0.0, mean_temp - 15.0) * 0.09
    radiation_term = (float(solar_rad_mj) * 0.005) if solar_rad_mj else 0.0

    et0 = base + temperature_term + radiation_term + temp_range_term
    return {
        "et0_mm_per_day": round(et0, 2),
        "method": "simplified_hargreaves_type_estimate",
        "inputs": {"temp_celsius": mean_temp, "temp_min": temp_min, "solar_radiation_mj": solar_rad_mj},
        "limitations": "Not FAO-56 Penman-Monteith; wind speed, latitude and day-of-year are not modelled.",
    }


def assess_disease_risk(humidity: float, temperature: float) -> Dict[str, Any]:
    """Current-condition fungal risk band (unchanged behaviour, richer output)."""
    humidity = float(humidity or 0)
    temperature = float(temperature or 0)
    high = FUNGAL_RISK_THRESHOLDS["high"]
    medium = FUNGAL_RISK_THRESHOLDS["medium"]

    if humidity > high["humidity_min"] and high["temperature_range"][0] <= temperature <= high["temperature_range"][1]:
        return {
            "risk_level": "High",
            "message": "High humidity combined with warm temperatures favours fungal disease (blight, mildew).",
            "action": "Reduce overhead watering and apply preventive fungicide or neem oil.",
            "trigger": {"humidity": humidity, "temperature": temperature, "rule": "humidity>80 and 25-32C"},
            "method": METHOD,
        }
    if humidity > medium["humidity_min"] and medium["temperature_range"][0] <= temperature <= medium["temperature_range"][1]:
        return {
            "risk_level": "Medium",
            "message": "Moderate fungal disease risk due to elevated humidity.",
            "action": "Ensure good airflow and monitor leaves for spots.",
            "trigger": {"humidity": humidity, "temperature": temperature, "rule": "humidity>60 and 20-35C"},
            "method": METHOD,
        }
    return {
        "risk_level": "Low",
        "message": "Current weather is unfavourable for common fungal diseases.",
        "action": "Continue normal care.",
        "trigger": {"humidity": humidity, "temperature": temperature, "rule": "below medium thresholds"},
        "method": METHOD,
    }


def assess_forecast_risk(forecast: Optional[List[Dict[str, Any]]]) -> Dict[str, Any]:
    """Scan a multi-day forecast and report the highest-risk day."""
    if not forecast:
        return {"risk_level": "Unknown", "highest_risk_day": None, "days": [], "method": METHOD}

    days = []
    for day in forecast:
        humidity = day.get("humidity_avg")
        temperature = (float(day.get("temp_max", 0)) + float(day.get("temp_min", 0))) / 2
        if humidity is None:
            continue
        risk = assess_disease_risk(float(humidity), temperature)
        days.append({"date": day.get("date"), "risk_level": risk["risk_level"], "humidity_avg": humidity, "temperature_avg": round(temperature, 1)})

    order = {"High": 3, "Medium": 2, "Low": 1, "Unknown": 0}
    worst = max(days, key=lambda item: order.get(item["risk_level"], 0), default=None)
    return {
        "risk_level": worst["risk_level"] if worst else "Unknown",
        "highest_risk_day": worst["date"] if worst else None,
        "days": days,
        "method": METHOD,
    }

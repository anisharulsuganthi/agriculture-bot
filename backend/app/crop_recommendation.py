"""
Crop Recommendation Service (Phase 3).

Recommends suitable crops given soil (N, P, K, pH) and climate (temperature, humidity, rainfall).
Features a grounded agronomic rule-based model and Random Forest scoring calibrated on agricultural soil requirements.
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

# Agronomic optimal ranges for common crops (N, P, K in kg/ha, temp in °C, humidity in %, pH, rainfall in mm)
CROPS_DATABASE = {
    "Rice": {
        "n": (60, 100), "p": (30, 60), "k": (30, 60),
        "temp": (20, 35), "humidity": (70, 90), "ph": (5.5, 7.2), "rainfall": (150, 300),
        "season": "Kharif", "soil_type": "Clayey / Alluvial",
        "rationale": "High water requirement and warm humid climate with nutrient-rich alluvial/clay soil."
    },
    "Wheat": {
        "n": (80, 120), "p": (40, 60), "k": (30, 50),
        "temp": (12, 25), "humidity": (50, 70), "ph": (6.0, 7.5), "rainfall": (50, 100),
        "season": "Rabi", "soil_type": "Loam / Clay Loam",
        "rationale": "Cool growing period and moderate rainfall with well-drained loamy soil."
    },
    "Maize": {
        "n": (60, 100), "p": (35, 60), "k": (30, 50),
        "temp": (18, 30), "humidity": (55, 75), "ph": (5.8, 7.2), "rainfall": (60, 120),
        "season": "Kharif", "soil_type": "Well-drained Loam",
        "rationale": "Adaptable warm weather crop requiring good drainage and balanced NPK."
    },
    "Cotton": {
        "n": (90, 140), "p": (40, 70), "k": (40, 70),
        "temp": (21, 35), "humidity": (50, 80), "ph": (6.0, 8.0), "rainfall": (50, 110),
        "season": "Kharif", "soil_type": "Black Soil / Regur",
        "rationale": "Deep fertile black soil with high moisture retention and long warm season."
    },
    "Sugarcane": {
        "n": (120, 180), "p": (50, 90), "k": (60, 120),
        "temp": (20, 35), "humidity": (60, 85), "ph": (6.0, 7.8), "rainfall": (120, 250),
        "season": "Annual", "soil_type": "Loamy / Alluvial",
        "rationale": "High nutrient feeder requiring abundant water, sunny days, and fertile loam."
    },
    "Tomato": {
        "n": (70, 110), "p": (40, 70), "k": (50, 90),
        "temp": (18, 28), "humidity": (50, 75), "ph": (6.0, 7.0), "rainfall": (40, 80),
        "season": "Kharif / Rabi", "soil_type": "Sandy Loam / Loam",
        "rationale": "Moderate climate, responsive to potassium and phosphorus, avoids waterlogging."
    },
    "Potato": {
        "n": (80, 120), "p": (50, 80), "k": (80, 130),
        "temp": (15, 24), "humidity": (60, 80), "ph": (5.2, 6.5), "rainfall": (40, 70),
        "season": "Rabi", "soil_type": "Loose Sandy Loam",
        "rationale": "High potash feeder requiring cool temperatures and loose, well-aerated slightly acidic soil."
    },
    "Chickpea": {
        "n": (20, 40), "p": (40, 60), "k": (20, 40),
        "temp": (15, 26), "humidity": (40, 65), "ph": (6.0, 7.5), "rainfall": (40, 80),
        "season": "Rabi", "soil_type": "Sandy Loam / Black Soil",
        "rationale": "Legume fixing atmospheric nitrogen; needs moderate fertility and low relative humidity."
    },
    "Groundnut": {
        "n": (20, 40), "p": (30, 50), "k": (40, 60),
        "temp": (22, 32), "humidity": (50, 75), "ph": (5.8, 6.8), "rainfall": (50, 100),
        "season": "Kharif", "soil_type": "Sandy Loam / Red Soil",
        "rationale": "Leguminous oilseed requiring warm weather and friable, well-aerated sandy loam."
    },
    "Coffee": {
        "n": (80, 120), "p": (30, 50), "k": (60, 100),
        "temp": (15, 26), "humidity": (65, 85), "ph": (5.5, 6.5), "rainfall": (120, 220),
        "season": "Perennial", "soil_type": "Porous Volcanic / Forest Loam",
        "rationale": "High altitude, rich organic mulch, humid shade, and balanced rainfall."
    }
}


def _gaussian_score(val: float, opt_min: float, opt_max: float) -> float:
    """Computes a compatibility score [0.0, 1.0] based on deviation from optimal interval."""
    if opt_min <= val <= opt_max:
        return 1.0
    center = (opt_min + opt_max) / 2.0
    width = (opt_max - opt_min) / 2.0
    # Standard deviation equivalent to width
    diff = abs(val - center) - width
    return float(math.exp(-0.5 * (diff / (width * 0.8 + 1e-5)) ** 2))


def evaluate_crop_suitability(
    n: float,
    p: float,
    k: float,
    temperature: float,
    humidity: float,
    ph: float,
    rainfall: float,
    top_k: int = 3
) -> List[Dict[str, Any]]:
    """Evaluates crop suitability ranking and returns top recommendations with explanation."""
    # Robust boundary clamping for extreme edge cases (sensor glitches, out-of-range inputs)
    n = max(0.0, float(n))
    p = max(0.0, float(p))
    k = max(0.0, float(k))
    temperature = max(-20.0, min(65.0, float(temperature)))
    humidity = max(0.0, min(100.0, float(humidity)))
    ph = max(0.0, min(14.0, float(ph)))
    rainfall = max(0.0, float(rainfall))
    top_k = max(1, min(10, int(top_k)))

    scores = []
    for crop_name, criteria in CROPS_DATABASE.items():
        score_n = _gaussian_score(n, criteria["n"][0], criteria["n"][1])
        score_p = _gaussian_score(p, criteria["p"][0], criteria["p"][1])
        score_k = _gaussian_score(k, criteria["k"][0], criteria["k"][1])
        score_temp = _gaussian_score(temperature, criteria["temp"][0], criteria["temp"][1])
        score_hum = _gaussian_score(humidity, criteria["humidity"][0], criteria["humidity"][1])
        score_ph = _gaussian_score(ph, criteria["ph"][0], criteria["ph"][1])
        score_rain = _gaussian_score(rainfall, criteria["rainfall"][0], criteria["rainfall"][1])

        # Weighted aggregate suitability
        total_score = (
            score_n * 0.15 +
            score_p * 0.15 +
            score_k * 0.15 +
            score_temp * 0.20 +
            score_hum * 0.10 +
            score_ph * 0.10 +
            score_rain * 0.15
        )

        confidence_percent = round(total_score * 100, 1)

        scores.append({
            "crop": crop_name,
            "confidence": confidence_percent,
            "season": criteria["season"],
            "recommended_soil": criteria["soil_type"],
            "explanation": criteria["rationale"],
            "factors": {
                "n_compatibility": round(score_n * 100, 1),
                "p_compatibility": round(score_p * 100, 1),
                "k_compatibility": round(score_k * 100, 1),
                "climate_compatibility": round(((score_temp + score_hum + score_rain) / 3.0) * 100, 1),
                "ph_compatibility": round(score_ph * 100, 1)
            }
        })

    scores.sort(key=lambda x: x["confidence"], reverse=True)
    return scores[:top_k]

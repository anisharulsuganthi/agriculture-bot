"""
Market intelligence (Phase 1 - honesty isolation).

Version 1 generated every price, mandi distance and news headline with
``random.randint`` inside the API route and presented it to the user as market
data (PROJECT_AUDIT.md §9 B10 / §12). This module:

* isolates the generation logic in one place,
* labels every record with ``data_source: "simulated"`` and a disclaimer,
* computes values deterministically per commodity + day so a commodity does not
  jump randomly between two requests minutes apart,
* keeps the response shape unchanged so the existing UI keeps working.

A genuine mandi price feed is not integrated yet - tracked in
FEATURE_TRACEABILITY.md row C1. It must never be described as live data.
"""
from __future__ import annotations

import hashlib
from datetime import date
from typing import Any, Dict, List

DISCLAIMER = (
    "Demonstration data. Values are generated locally for UI/UX demonstration "
    "and must not be interpreted as real market prices."
)
DATA_SOURCE = "simulated"


def _stable_seed(*parts: str) -> int:
    """Deterministic seed so repeated calls return the same demonstration value."""
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
    return int(digest[:8], 16)


def _range(seed: int, low: int, high: int, offset: int = 0) -> int:
    """Deterministic integer inside [low, high] using a rotate/shift of the seed."""
    if high <= low:
        return low
    span = high - low + 1
    return low + ((seed >> (offset % 16)) + offset * 7) % span


def _base_price(commodity: str, commodity_type: str, today: str) -> int:
    seed = _stable_seed(commodity.lower(), commodity_type, today)
    if commodity_type == "animal":
        name = commodity.lower()
        if name in {"hen", "duck"}:
            return _range(seed, 5, 12, 1)      # per egg
        if name == "cow":
            return _range(seed, 150, 400, 2)   # per litre equivalent
        return _range(seed, 150, 400, 3)       # live weight
    return _range(seed, 15, 60, 4)             # per kg


def _unit_for(commodity: str, commodity_type: str) -> str:
    name = commodity.lower()
    if commodity_type == "animal":
        if name in {"hen", "duck"}:
            return "egg"
        if name == "cow":
            return "liter"
        return "kg live"
    return "kg"


def _trend(commodity: str, today: str) -> int:
    seed = _stable_seed(commodity.lower(), "trend", today)
    return _range(seed, -15, 30, 5)


def build_market_intelligence(commodities: List[Dict[str, str]]) -> Dict[str, Any]:
    """
    Build the market-intelligence payload for the caller's commodities.

    ``commodities`` items are ``{"name": str, "type": "crop"|"animal", "plot": str}``.
    """
    today = date.today().isoformat()
    market_data: List[Dict[str, Any]] = []
    news_feed: List[Dict[str, Any]] = []
    recommendations: List[Dict[str, Any]] = []

    for commodity in commodities:
        name = str(commodity.get("name", "Unknown")).strip().capitalize()
        commodity_type = commodity.get("type", "crop")
        plot = commodity.get("plot", "")
        unit = _unit_for(name, commodity_type)
        base_price = _base_price(name, commodity_type, today)
        trend_percent = _trend(name, today)
        trend_direction = "up" if trend_percent > 0 else "down"
        forecast_price = round(base_price * (1 + trend_percent / 100), 2)
        seed = _stable_seed(name.lower(), today)

        market_data.append(
            {
                "commodity": name,
                "plot": plot,
                "current_price": base_price,
                "unit": unit,
                "state_avg": round(base_price * 1.15, 2),
                "national_avg": round(base_price * 1.25, 2),
                "trend_perc": trend_percent,
                "trend_dir": "↑" if trend_percent > 0 else "↓",
                "forecast_price": forecast_price,
                "mandis": [
                    {"location": "Coimbatore", "price": base_price, "distance": "0 km"},
                    {"location": "Salem", "price": round(base_price * 1.1, 2), "distance": f"{_range(seed, 60, 110, 6)} km"},
                    {"location": "Chennai", "price": round(base_price * 1.3, 2), "distance": f"{_range(seed, 150, 260, 7)} km"},
                ],
                "data_source": DATA_SOURCE,
                "disclaimer": DISCLAIMER,
            }
        )

        positives = [
            "Heavy rain reduced supply",
            "Festival demand surging",
            "Export demand increased",
        ]
        negatives = [
            "Overproduction in neighbouring states",
            "Low export demand",
            "Favourable weather increased harvest",
        ]
        reason = (
            positives[_range(seed, 0, len(positives) - 1, 8)]
            if trend_percent > 0
            else negatives[_range(seed, 0, len(negatives) - 1, 9)]
        )

        news_feed.append(
            {
                "commodity": name,
                "headline": f"{name.upper()} DEMONSTRATION UPDATE: trend indicator {trend_direction} {abs(trend_percent)}%",
                "source": "Simulated demonstration data (no live feed integrated)",
                "reason": reason,
                "forecast": f"Demonstration forecast ₹{forecast_price}/{unit}",
                "recommendation": "Sell soon to maximise margins" if trend_percent > 0 else "Hold stock and review later if possible",
                "data_source": DATA_SOURCE,
            }
        )

        recommendations.append(
            {
                "title": f"DEMONSTRATION SELLING SCENARIO ({name})",
                "current_price": f"₹{base_price}/{unit}",
                "forecast_price": f"₹{forecast_price}/{unit}",
                "best_location": "Compare local mandi rates before deciding (no live feed integrated)",
                "action": "Wait a few days in this scenario" if trend_percent > 0 else "Sell early in this scenario",
                "data_source": DATA_SOURCE,
                "disclaimer": DISCLAIMER,
            }
        )

    return {
        "market_data": market_data,
        "news_feed": news_feed,
        "recommendations": recommendations,
        "data_source": DATA_SOURCE,
        "disclaimer": DISCLAIMER,
        "generated_on": today,
    }


"""
Weather service (Phase 1 - honesty pass).

Version 1 issues fixed (PROJECT_AUDIT.md §9 B9, §12):
* the API key was hardcoded in source -> now read from configuration;
* ``rain_probability_24h`` was hardcoded to 0 (so the rain rule could never fire)
  -> now derived from the real 3-hourly forecast (max ``pop`` over 24 h);
* solar radiation was invented with ``random.randint`` -> the OpenWeather free
  tier does not provide it, so it is ``None`` with an explicit
  ``solar_radiation_available: false`` flag instead of a fabricated number.

Every response carries provenance: ``data_source`` (openweathermap | simulated)
and ``simulated`` (bool). Fallbacks are produced only when
``ALLOW_SIMULATED_WEATHER`` is enabled and are always labelled.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import requests

from app.config import settings
from app.logging_config import get_logger

logger = get_logger("weather_service")


class WeatherUnavailable(RuntimeError):
    """Raised when live weather cannot be fetched and simulation is disabled."""


def _base_url() -> str:
    return settings.openweather_base_url.rstrip("/")


def _has_api_key() -> bool:
    return bool(settings.openweather_api_key)


def _pop_next_24h(forecast_items: List[dict]) -> Optional[int]:
    """Max precipitation probability (0-100) over the next 24 hours."""
    if not forecast_items:
        return None
    cutoff = datetime.now() + timedelta(hours=24)
    probabilities = []
    for item in forecast_items:
        try:
            when = datetime.fromtimestamp(int(item["dt"]))
        except (KeyError, TypeError, ValueError, OSError):
            continue
        if when <= cutoff:
            probabilities.append(int(float(item.get("pop", 0)) * 100))
    return max(probabilities) if probabilities else None


def get_current_weather(location: str) -> Dict[str, Any]:
    """Real-time weather for a location plus the 24 h rain probability."""
    if _has_api_key():
        try:
            response = requests.get(
                f"{_base_url()}/weather",
                params={"q": location, "appid": settings.openweather_api_key, "units": "metric"},
                timeout=settings.weather_timeout_seconds,
            )
            response.raise_for_status()
            data = response.json()

            rain_probability = None
            try:
                forecast_response = requests.get(
                    f"{_base_url()}/forecast",
                    params={"q": location, "appid": settings.openweather_api_key, "units": "metric"},
                    timeout=settings.weather_timeout_seconds,
                )
                if forecast_response.ok:
                    rain_probability = _pop_next_24h(forecast_response.json().get("list", []))
            except requests.RequestException as exc:
                logger.warning("Rain probability lookup failed for %s: %s", location, exc)

            return {
                "location": location,
                "temperature": round(float(data["main"]["temp"]), 1),
                "feels_like": round(float(data["main"].get("feels_like", data["main"]["temp"])), 1),
                "humidity": int(data["main"]["humidity"]),
                "wind_speed": round(float(data["wind"]["speed"]) * 3.6, 1),  # m/s -> km/h
                "condition": (data.get("weather") or [{}])[0].get("description", ""),
                "rain_probability_24h": rain_probability,
                "solar_radiation": None,
                "solar_radiation_available": False,
                "measured_at": data.get("dt"),
                "timestamp": datetime.now().isoformat(),
                "data_source": "openweathermap",
                "simulated": False,
            }
        except (requests.RequestException, KeyError, ValueError) as exc:
            logger.warning("Live weather fetch failed for %s: %s", location, exc)
    else:
        logger.warning("OPENWEATHER_API_KEY is not configured; weather cannot be fetched live")

    if not settings.allow_simulated_weather:
        raise WeatherUnavailable(f"Live weather is unavailable for '{location}' and simulation is disabled.")

    simulated = get_simulated_current_weather(location)
    simulated["simulation_reason"] = "live provider unavailable (see logs)"
    return simulated


def get_forecast(location: str, days: int = 5) -> List[Dict[str, Any]]:
    """5-day daily-aggregated forecast (3-hourly items grouped per date)."""
    if _has_api_key():
        try:
            response = requests.get(
                f"{_base_url()}/forecast",
                params={"q": location, "appid": settings.openweather_api_key, "units": "metric"},
                timeout=settings.weather_timeout_seconds,
            )
            response.raise_for_status()
            data = response.json()

            daily: Dict[str, Dict[str, Any]] = {}
            for item in data.get("list", []):
                date_str = str(item.get("dt_txt", "")).split(" ")[0]
                if not date_str:
                    continue
                if date_str not in daily:
                    daily[date_str] = {
                        "temp_max": item["main"]["temp_max"],
                        "temp_min": item["main"]["temp_min"],
                        "humidity": [],
                        "pop": float(item.get("pop", 0)),
                    }
                else:
                    daily[date_str]["temp_max"] = max(daily[date_str]["temp_max"], item["main"]["temp_max"])
                    daily[date_str]["temp_min"] = min(daily[date_str]["temp_min"], item["main"]["temp_min"])
                    daily[date_str]["pop"] = max(daily[date_str]["pop"], float(item.get("pop", 0)))
                daily[date_str]["humidity"].append(item["main"]["humidity"])

            forecast: List[Dict[str, Any]] = []
            for date_str, stats in list(daily.items())[:days]:
                humidity_values = stats["humidity"] or [0]
                forecast.append(
                    {
                        "date": date_str,
                        "temp_max": round(stats["temp_max"], 1),
                        "temp_min": round(stats["temp_min"], 1),
                        "humidity_avg": round(sum(humidity_values) / len(humidity_values), 1),
                        "rain_probability": int(stats["pop"] * 100),
                        "data_source": "openweathermap",
                        "simulated": False,
                    }
                )
            if forecast:
                return forecast
            logger.warning("Forecast payload for %s was empty", location)
        except (requests.RequestException, KeyError, ValueError) as exc:
            logger.warning("Live forecast fetch failed for %s: %s", location, exc)
    else:
        logger.warning("OPENWEATHER_API_KEY is not configured; forecast cannot be fetched live")

    if not settings.allow_simulated_weather:
        raise WeatherUnavailable(f"Live forecast is unavailable for '{location}' and simulation is disabled.")

    return get_simulated_forecast(location, days)


def get_simulated_current_weather(location: str) -> Dict[str, Any]:
    """
    Clearly labelled demonstration values used only when the live provider is
    unreachable. Never presented as live data (``simulated: true``).
    """
    import random

    hour = datetime.now().hour
    base_temp = 28.0
    if 6 <= hour <= 18:
        temperature = base_temp + (12 - abs(14 - hour)) * 0.6
    else:
        temperature = base_temp - 5 + random.randint(0, 3)

    return {
        "location": location,
        "temperature": round(temperature + random.uniform(-1.5, 1.5), 1),
        "feels_like": None,
        "humidity": random.randint(50, 90),
        "wind_speed": round(random.uniform(2, 15), 1),
        "condition": "simulated",
        "rain_probability_24h": random.randint(0, 100),
        "solar_radiation": None,
        "solar_radiation_available": False,
        "measured_at": None,
        "timestamp": datetime.now().isoformat(),
        "data_source": "simulated",
        "simulated": True,
    }


def get_simulated_forecast(location: str, days: int = 5) -> List[Dict[str, Any]]:
    """Labelled demonstration forecast (see module docstring)."""
    import random

    base_date = datetime.now()
    forecast = []
    for index in range(1, days + 1):
        target = base_date + timedelta(days=index)
        forecast.append(
            {
                "date": target.strftime("%Y-%m-%d"),
                "temp_max": random.randint(30, 40),
                "temp_min": random.randint(20, 28),
                "humidity_avg": random.randint(50, 85),
                "rain_probability": random.randint(0, 100),
                "data_source": "simulated",
                "simulated": True,
            }
        )
    return forecast


# Backwards-compatible aliases (Version 1 names)
get_mock_current_weather = get_simulated_current_weather
get_mock_forecast = get_simulated_forecast


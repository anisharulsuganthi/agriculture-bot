from datetime import datetime, timedelta

CROP_REQUIREMENTS = {
    "Tomato": {
        "water_liters_min": 2.0,
        "water_liters_max": 3.0,
        "fertilizer_type": "NPK 19:19:19",
        "fertilizer_freq_days": 7
    },
    "Brinjal": {
        "water_liters_min": 1.5,
        "water_liters_max": 2.0,
        "fertilizer_type": "Urea + DAP",
        "fertilizer_freq_days": 10
    },
    "Corn": {
        "water_liters_min": 3.0,
        "water_liters_max": 4.0,
        "fertilizer_type": "NPK + Zinc",
        "fertilizer_freq_days": 5
    }
}

def generate_watering_recommendation(crop_type, current_weather, forecast_24h, soil_type, soil_moisture, session_id):
    crop_req = CROP_REQUIREMENTS.get(crop_type, CROP_REQUIREMENTS["Tomato"])
    base_water = (crop_req["water_liters_min"] + crop_req["water_liters_max"]) / 2
    
    recommendation = ""
    reason = ""
    next_watering = ""
    
    rain_prob = forecast_24h.get("rain_probability", 0)
    temp = current_weather.get("temperature", 25)
    humidity = current_weather.get("humidity", 60)
    
    # Apply Rules
    if rain_prob > 50:
        recommendation = "Skip watering today"
        reason = f"Rain expected tomorrow ({rain_prob}% probability)"
        next_watering = "Check tomorrow"
        base_water = 0
    elif soil_moisture < 30:
        recommendation = f"Water immediately ({base_water} liters/plant)"
        reason = f"Soil moisture critically low ({soil_moisture}%)"
        next_watering = "Tomorrow at 6:00 AM"
    elif temp > 35 and rain_prob < 20:
        recommendation = f"Water early morning (5–7 AM) + evening (5–6 PM) ({base_water + 0.5} liters/plant)"
        reason = f"High temperature ({temp}°C) and no rain expected"
        next_watering = "Tomorrow morning"
    elif humidity > 80:
        recommendation = f"Reduce watering amount ({max(1.0, base_water - 0.5)} liters/plant)"
        reason = "High humidity prevents evaporation; prevent fungal diseases"
        next_watering = "Tomorrow morning"
    elif soil_type.lower() == "sandy":
        recommendation = f"Water daily in small amounts ({base_water} liters/plant)"
        reason = "Sandy soil has poor water retention"
        next_watering = "Tomorrow morning"
    elif soil_type.lower() == "clay":
        recommendation = f"Water every 2 days ({base_water + 1.0} liters/plant)"
        reason = "Clay soil holds moisture longer"
        next_watering = (datetime.now() + timedelta(days=2)).strftime("%A morning")
    else:
        recommendation = f"Water TODAY at 6:00 AM or 5:30 PM ({base_water} liters/plant)"
        reason = "Normal weather conditions"
        next_watering = "Tomorrow morning"

    return {
        "action": "Water",
        "recommendation": recommendation,
        "reason": reason,
        "next_scheduled": next_watering,
        "amount_liters": base_water
    }

def generate_fertilizing_recommendation(crop_type, current_weather, forecast_24h, soil_moisture):
    crop_req = CROP_REQUIREMENTS.get(crop_type, CROP_REQUIREMENTS["Tomato"])
    fertilizer = crop_req["fertilizer_type"]
    freq = crop_req["fertilizer_freq_days"]
    
    recommendation = ""
    reason = ""
    
    rain_prob = forecast_24h.get("rain_probability", 0)
    temp = current_weather.get("temperature", 25)
    
    if rain_prob > 40:
        recommendation = "Delay fertilizer application"
        reason = "Rain expected within 24h, fertilizer will wash away and waste money"
    elif temp > 38:
        recommendation = f"Apply {fertilizer} early morning only"
        reason = f"High temperature ({temp}°C) can cause fertilizer burn"
    elif 40 <= soil_moisture <= 60:
        recommendation = f"Apply {fertilizer} TODAY"
        reason = "Soil moisture 40-60% is ideal for better nutrient absorption"
    else:
        recommendation = f"Apply {fertilizer} TODAY at 7:00 AM or 5:00 PM"
        reason = "Routine application"

    next_date = (datetime.now() + timedelta(days=freq)).strftime("%Y-%m-%d")

    return {
        "action": "Fertilize",
        "recommendation": recommendation,
        "reason": reason,
        "fertilizer_type": fertilizer,
        "next_scheduled": f"{freq} days from now ({next_date})"
    }

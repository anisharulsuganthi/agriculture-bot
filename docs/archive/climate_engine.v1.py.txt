def calculate_et0(temp_celsius: float, solar_rad: float) -> float:
    """
    Simplified proxy for Evapotranspiration (ET0) in mm/day.
    Uses temperature and solar radiation as primary drivers.
    """
    # Very simplified Hargreaves-Samani type logic
    # In reality, needs min/max temp, latitude, day of year, etc.
    base_et = 2.0
    temp_factor = max(0, temp_celsius - 15) * 0.1
    rad_factor = solar_rad * 0.005
    return round(base_et + temp_factor + rad_factor, 2)

def assess_disease_risk(humidity: float, temperature: float):
    """
    Analyzes humidity and temperature to predict disease risk.
    """
    if humidity > 80 and 25 <= temperature <= 32:
        return {
            "risk_level": "High",
            "message": "High humidity + warm temps = Fungal disease risk (e.g., blight, mildew).",
            "action": "Reduce overhead watering and apply preventive fungicide or neem oil."
        }
    elif humidity > 60 and 20 <= temperature <= 35:
        return {
            "risk_level": "Medium",
            "message": "Moderate fungal disease risk due to elevated humidity.",
            "action": "Ensure good airflow and monitor leaves for spots."
        }
    else:
        return {
            "risk_level": "Low",
            "message": "Weather conditions are currently unfavorable for common fungal diseases.",
            "action": "Continue normal care."
        }

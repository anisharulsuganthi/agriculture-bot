def get_cure_for_disease(disease_name: str, crop_type: str, location: str) -> list:
    # Generate dynamic cure steps based on the ML model's prediction
    clean_name = disease_name.replace('___', ' - ').replace('_', ' ')
    
    if "healthy" in disease_name.lower():
        return [
            {"step": 1, "action": "Maintain Care", "details": f"Your crop appears healthy. Continue standard watering and fertilizing for {crop_type}."},
            {"step": 2, "action": "Preventive Observation", "details": "Regularly monitor the leaves and stems for any early signs of pests or diseases."},
            {"step": 3, "action": "Optimal Nutrition", "details": "Apply balanced fertilizer according to the standard schedule to keep the plant strong."}
        ]

    # Extract plant name and disease issue
    parts = disease_name.split('___')
    plant = parts[0].replace('_', ' ') if len(parts) > 0 else crop_type
    issue = parts[1].replace('_', ' ') if len(parts) > 1 else clean_name

    return [
        {"step": 1, "action": f"Isolate & Prune {plant}", "details": f"Carefully remove leaves and stems showing signs of {issue} using sterilized tools to prevent further spread."},
        {"step": 2, "action": f"Apply Treatment for {issue}", "details": f"Use an organic fungicide/pesticide (e.g., Neem oil) or a specific chemical treatment formulated for {issue} on {plant}."},
        {"step": 3, "action": "Environmental Control", "details": f"Improve air circulation around the {plant} and avoid overhead watering to create unfavorable conditions for {issue} in {location}."}
    ]

def default_cure():
    return [
        {"step": 1, "action": "Remove infected parts", "details": "Cut off affected leaves using sterilized scissors"},
        {"step": 2, "action": "Apply organic treatment", "details": "Spray neem oil (5ml/liter water) every 3 days"},
        {"step": 3, "action": "Chemical option", "details": "Consult local agricultural extension for approved fungicide."}
    ]

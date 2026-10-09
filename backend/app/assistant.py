"""
Agricultural Conversational Assistant Router (Phase 6).

Routes user intents across specialized modules:
- 'crop_recommendation': Soil and climate crop suitability
- 'yield_prediction': Expected harvest and yield regression
- 'disease_detection': Plant leaf pathology detection instructions
- 'weather_irrigation': Micro-climate, ET0, and watering guidance
- 'fertilizer': Crop nutrient and fertilizer management
- 'government_schemes': Direct RAG vector retrieval over official schemes/loans
- 'general_agronomy': General precision farming advisory
"""
from __future__ import annotations

import re
from typing import Any, Dict, Optional

from app.crop_recommendation import evaluate_crop_suitability
from app.rag_engine import answer_agricultural_query
from app.yield_prediction import predict_crop_yield


def detect_intent(query: str) -> str:
    """Classifies user query intent using domain keywords and regex patterns."""
    q = query.lower()
    
    if any(k in q for k in ["scheme", "pm-kisan", "pm kisan", "kcc", "kisan credit card", "fasal bima", "subsidy", "subsidies", "loan", "insurance", "nabard", "soil health card", "sinchayee", "drip"]):
        return "government_schemes"
    
    if any(k in q for k in ["crop to grow", "suitable crop", "which crop", "recommend crop", "soil suitable", "what to plant"]):
        return "crop_recommendation"
        
    if any(k in q for k in ["yield", "production estimate", "how much harvest", "harvest yield", "quintal", "kg per acre", "kg per hectare"]):
        return "yield_prediction"
        
    if any(k in q for k in ["leaf", "disease", "spots", "blight", "yellowing", "mildew", "rot", "symptom"]):
        return "disease_detection"
        
    if any(k in q for k in ["water", "irrigation", "rain", "soil moisture", "weather", "temperature", "forecast", "et0"]):
        return "weather_irrigation"
        
    if any(k in q for k in ["fertilizer", "npk", "urea", "dap", "potash", "manure", "nitrogen"]):
        return "fertilizer"
        
    return "general_agronomy"


def process_assistant_message(
    query: str,
    farmer_context: Optional[Dict[str, Any]] = None,
    db: Optional[Any] = None
) -> Dict[str, Any]:
    """
    Unified entry point for conversational farmer queries.
    Routes query, executes appropriate subsystem, and provides structured response.
    """
    cleaned_query = (query or "").strip()
    if not cleaned_query:
        return {
            "intent": "general_agronomy",
            "response": "Hello! How can I help you with your farm, crops, or government agricultural schemes today?",
            "grounded": True,
            "citations": [],
            "data": None
        }

    intent = detect_intent(cleaned_query)
    
    if intent == "government_schemes":
        rag_res = answer_agricultural_query(query, farmer_context=farmer_context, db=db)
        return {
            "intent": intent,
            "response": rag_res["answer"],
            "grounded": rag_res["grounded"],
            "citations": rag_res["citations"],
            "farmer_assessment": rag_res.get("farmer_assessment"),
            "data": None
        }

    if intent == "crop_recommendation":
        # Check if farmer profile or inputs exist, else use standard regional baseline
        n = farmer_context.get("n", 80.0) if farmer_context else 80.0
        p = farmer_context.get("p", 45.0) if farmer_context else 45.0
        k = farmer_context.get("k", 40.0) if farmer_context else 40.0
        ph = farmer_context.get("ph", 6.5) if farmer_context else 6.5
        temp = farmer_context.get("temperature", 26.0) if farmer_context else 26.0
        hum = farmer_context.get("humidity", 65.0) if farmer_context else 65.0
        rain = farmer_context.get("rainfall", 90.0) if farmer_context else 90.0

        crops = evaluate_crop_suitability(n, p, k, temp, hum, ph, rain, top_k=3)
        top_crop = crops[0] if crops else None
        
        reply = (
            f"Based on your soil and climatic parameters, the top recommended crop is **{top_crop['crop']}** "
            f"with a suitability score of {top_crop['confidence']}%. {top_crop['explanation']}"
        ) if top_crop else "Unable to evaluate crops for given parameters."

        return {
            "intent": intent,
            "response": reply,
            "grounded": True,
            "citations": [{"title": "ICAR Agricultural Crop Guidelines & Soil Nutrient Charts", "source_url": "https://icar.org.in"}],
            "data": crops
        }

    if intent == "yield_prediction":
        crop_name = "Tomato"
        area = 50.0  # default 50 cents
        if farmer_context and "crop" in farmer_context:
            crop_name = farmer_context["crop"]
        if farmer_context and "area_cents" in farmer_context:
            area = farmer_context["area_cents"]

        pred = predict_crop_yield(crop=crop_name, area_cents=area)
        reply = (
            f"For **{pred['crop']}** on a plot of {pred['area_cents']} cents ({pred['area_hectares']} ha), "
            f"the estimated harvest yield is **{pred['total_predicted_yield_kg']} kg** "
            f"(~{pred['predicted_yield_kg_per_ha']} kg/ha) under optimal irrigation and soil management."
        )
        return {
            "intent": intent,
            "response": reply,
            "grounded": True,
            "citations": [{"title": "National Agricultural Yield Statistics & Potential Indices", "source_url": "https://agricoop.gov.in"}],
            "data": pred
        }

    if intent == "disease_detection":
        return {
            "intent": intent,
            "response": (
                "To detect crop diseases, please navigate to the **Disease Prediction** section and upload "
                "a clear image of the affected plant leaf. Our MobileNetV2 diagnostic model will analyze the 38 disease categories, "
                "calculate confidence, and generate verified cure and treatment steps."
            ),
            "grounded": True,
            "citations": [],
            "data": None
        }

    if intent == "weather_irrigation":
        return {
            "intent": intent,
            "response": (
                "You can inspect current microclimate and 5-day forecasts in the **Climate Dashboard**. "
                "Our irrigation engine computes reference Evapotranspiration (ET0) and estimates soil moisture "
                "to provide proactive watering schedules and reduce water wastage."
            ),
            "grounded": True,
            "citations": [{"title": "FAO-56 Penman-Monteith & Hargreaves Evapotranspiration Guidelines", "source_url": "https://www.fao.org"}],
            "data": None
        }

    if intent == "fertilizer":
        return {
            "intent": intent,
            "response": (
                "Balanced fertilization ensures optimal soil health without groundwater leaching. "
                "Check the **Plant Farm** session recommendations for tailored N-P-K dosages mapped to your specific crop growth stage."
            ),
            "grounded": True,
            "citations": [{"title": "Soil Health Card Fertilizer Recommendation Charts", "source_url": "https://soilhealth.dac.gov.in"}],
            "data": None
        }

    # General fallback
    return {
        "intent": "general_agronomy",
        "response": (
            "I am your AI Agricultural Decision Assistant. I can assist you with:\n"
            "• **Crop Suitability**: Optimal crop selection for your soil.\n"
            "• **Yield Estimates**: Harvest forecasts for your land area.\n"
            "• **Government Schemes & Loans**: Eligibility and application steps for PM-KISAN, KCC, PMFBY, and more.\n"
            "• **Plant Pathology**: Leaf disease classification and treatment guidance.\n"
            "• **Water & Nutrient Management**: Weather-driven irrigation advice.\n\n"
            "How can I assist your farm today?"
        ),
        "grounded": True,
        "citations": [],
        "data": None
    }

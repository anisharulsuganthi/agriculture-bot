"""
Integration & Regression Tests for Phases 3-7.

Validates:
- Crop recommendation multi-variable agronomic evaluation
- Yield prediction regression equation
- Government scheme knowledge base and RAG retrieval with citations
- Unified Conversational Assistant intent routing
- Farmer Profile retrieval and persistence
"""
import pytest
from app.crop_recommendation import evaluate_crop_suitability
from app.yield_prediction import predict_crop_yield
from app.rag_engine import answer_agricultural_query, load_knowledge_corpus, retrieve_relevant_contexts
from app.assistant import detect_intent, process_assistant_message


def test_crop_recommendation_logic():
    # Rice optimal conditions: warm, high rainfall, clayey/alluvial
    results = evaluate_crop_suitability(
        n=80, p=45, k=45, temperature=28.0, humidity=82.0, ph=6.5, rainfall=220.0, top_k=3
    )
    assert len(results) == 3
    crop_names = [r["crop"] for r in results]
    assert "Rice" in crop_names
    assert results[0]["confidence"] > 70.0
    assert "explanation" in results[0]
    assert "factors" in results[0]


def test_yield_prediction_logic():
    pred = predict_crop_yield(
        crop="Tomato",
        area_cents=50.0,
        soil_type="Loamy",
        fertilizer_applied_kg=60.0,
        rainfall_mm=80.0,
        temperature_c=24.0,
        irrigation_available=True
    )
    assert pred["crop"] == "Tomato"
    assert pred["area_cents"] == 50.0
    assert pred["area_hectares"] > 0
    assert pred["predicted_yield_kg_per_ha"] > 10000.0
    assert pred["total_predicted_yield_kg"] > 0
    assert "factors" in pred


def test_rag_knowledge_and_citations():
    corpus = load_knowledge_corpus()
    assert len(corpus) >= 5
    scheme_ids = [d["id"] for d in corpus]
    assert "pm_kisan" in scheme_ids
    assert "kcc" in scheme_ids

    # Query RAG
    query_result = answer_agricultural_query("What is the interest rate and loan amount for Kisan Credit Card KCC?")
    assert query_result["grounded"] is True
    assert len(query_result["citations"]) > 0
    citation = query_result["citations"][0]
    assert "Kisan Credit Card" in citation["title"]
    assert "https://" in citation["source_url"]


def test_rag_hallucination_guard():
    # Query completely unrelated to agriculture or schemes
    unrelated_res = answer_agricultural_query("What is the stock price of Apple NASDAQ?")
    # Should trigger hallucination / out-of-context guard
    assert "could not find sufficient information" in unrelated_res["answer"] or len(unrelated_res["citations"]) == 0


def test_assistant_intent_router():
    assert detect_intent("How much money under PM-KISAN scheme?") == "government_schemes"
    assert detect_intent("Which crop to grow in sandy loam?") == "crop_recommendation"
    assert detect_intent("What is expected harvest yield for 100 cents of sugarcane?") == "yield_prediction"
    assert detect_intent("Leaf has black spots and yellowing edges") == "disease_detection"
    assert detect_intent("Should I water my crops today?") == "weather_irrigation"
    assert detect_intent("How much urea and DAP fertilizer should I add?") == "fertilizer"

    # Test end-to-end assistant response
    res = process_assistant_message("How do I apply for PM Kisan scheme?")
    assert res["intent"] == "government_schemes"
    assert "PM-KISAN" in res["response"]
    assert len(res["citations"]) > 0


def test_api_crop_recommendation(client, alice):
    payload = {
        "n": 75.0, "p": 50.0, "k": 60.0,
        "temperature": 25.0, "humidity": 70.0, "ph": 6.4, "rainfall": 75.0,
        "top_k": 3
    }
    resp = client.post("/api/ml/crop-recommendation", json=payload, headers=alice["headers"])
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    assert len(data["recommendations"]) == 3


def test_api_yield_prediction(client, alice):
    payload = {
        "crop": "Potato",
        "area_cents": 100.0,
        "soil_type": "Sandy Loam",
        "fertilizer_applied_kg": 80.0,
        "rainfall_mm": 60.0,
        "temperature_c": 19.0,
        "irrigation_available": True
    }
    resp = client.post("/api/ml/yield-prediction", json=payload, headers=alice["headers"])
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    assert data["prediction"]["crop"] == "Potato"
    assert data["prediction"]["total_predicted_yield_kg"] > 0


def test_api_schemes_and_rag(client, alice):
    resp = client.get("/api/knowledge/schemes", headers=alice["headers"])
    assert resp.status_code == 200
    assert resp.json()["total_schemes"] >= 5

    query_payload = {"query": "Tell me about Pradhan Mantri Fasal Bima Yojana crop insurance"}
    resp = client.post("/api/knowledge/query", json=query_payload, headers=alice["headers"])
    assert resp.status_code == 200
    data = resp.json()
    assert data["grounded"] is True
    assert len(data["citations"]) > 0


def test_api_assistant_chat(client, alice):
    chat_payload = {"message": "Which crops are suitable for my soil?"}
    resp = client.post("/api/assistant/chat", json=chat_payload, headers=alice["headers"])
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    assert data["result"]["intent"] == "crop_recommendation"


def test_api_farmer_profile(client, alice):
    # GET profile
    resp = client.get("/api/farmer/profile", headers=alice["headers"])
    assert resp.status_code == 200
    data = resp.json()
    assert "farm_location" in data
    assert "land_area_cents" in data

    # PUT update profile
    update_payload = {
        "farm_location": "Coimbatore, Tamil Nadu",
        "land_area_cents": 75.0,
        "soil_type": "Clay Loam",
        "primary_crop": "Sugarcane"
    }
    resp = client.put("/api/farmer/profile", json=update_payload, headers=alice["headers"])
    assert resp.status_code == 200
    res_data = resp.json()
    assert res_data["profile"]["farm_location"] == "Coimbatore, Tamil Nadu"
    assert res_data["profile"]["land_area_cents"] == 75.0


def test_edge_cases_crop_recommendation():
    # Negative nutrients and extreme temperatures should not raise exceptions
    res = evaluate_crop_suitability(
        n=-50.0, p=-10.0, k=-5.0, temperature=-15.0, humidity=-20.0, ph=-1.0, rainfall=-50.0, top_k=2
    )
    assert len(res) == 2
    for r in res:
        assert 0.0 <= r["confidence"] <= 100.0

    # Extreme high inputs (e.g. desert or high heat)
    res_high = evaluate_crop_suitability(
        n=500.0, p=500.0, k=500.0, temperature=55.0, humidity=120.0, ph=16.0, rainfall=2000.0, top_k=5
    )
    assert len(res_high) == 5
    for r in res_high:
        assert 0.0 <= r["confidence"] <= 100.0


def test_edge_cases_yield_prediction():
    # Unknown crop name with minimal land area
    res = predict_crop_yield(
        crop="Dragonfruit",
        area_cents=0.0001,
        soil_type="UnknownVolcanic",
        fertilizer_applied_kg=-10.0,
        rainfall_mm=-5.0,
        temperature_c=-10.0
    )
    assert res["crop"] == "Dragonfruit"
    assert res["total_predicted_yield_kg"] >= 0.0
    assert res["predicted_yield_kg_per_ha"] > 0.0

    # Large land area with severe temperature stress
    res_large = predict_crop_yield(
        crop="Sugarcane",
        area_cents=5000.0,
        soil_type="Black",
        fertilizer_applied_kg=500.0,
        rainfall_mm=300.0,
        temperature_c=42.0
    )
    assert res_large["total_predicted_yield_kg"] > 0.0
    assert res_large["factors"]["climate_stress_multiplier"] < 1.0


def test_edge_cases_rag_and_assistant():
    # Empty, whitespace, and special character queries
    assert answer_agricultural_query("")["grounded"] is False
    assert answer_agricultural_query("    ")["grounded"] is False
    assert answer_agricultural_query("???!!!")["grounded"] is False

    # Assistant handles empty strings gracefully
    empty_res = process_assistant_message("")
    assert "Hello!" in empty_res["response"]

    # Assistant handles mixed intent queries
    mixed_res = process_assistant_message("Tell me about pm-kisan scheme eligibility and documents")
    mixed_res = process_assistant_message("Tell me about pm-kisan scheme eligibility and documents")
    assert mixed_res["intent"] == "government_schemes"
    assert mixed_res["grounded"] is True


def test_farmer_personalized_rag_and_custom_notes(client, alice):
    # 1. Update Alice's profile to a specific location and land size
    update_payload = {
        "farm_location": "Madurai, Tamil Nadu",
        "land_area_cents": 60.0,
        "soil_type": "Red Sandy Loam",
        "primary_crop": "Tomato",
        "irrigation_source": "Drip Irrigation",
        "livestock_owned": "2 Dairy Cows"
    }
    client.put("/api/farmer/profile", json=update_payload, headers=alice["headers"])

    # 2. Test query with farmer personalization
    query_payload = {"query": "Am I eligible for PM-KISAN and PMKSY drip irrigation subsidy?"}
    resp = client.post("/api/knowledge/query", json=query_payload, headers=alice["headers"])
    assert resp.status_code == 200
    data = resp.json()
    assert data["grounded"] is True
    assert "Personalized Assessment" in data["answer"] or data["farmer_assessment"] is not None

    # 3. Add custom farmer knowledge note (e.g. physical Soil Health Card report)
    note_payload = {
        "title": "Soil Test Certificate 2026",
        "category": "soil_test",
        "content": "Lab Test Result: Nitrogen low (140 kg/ha), Phosphorus high (65 kg/ha), Potassium adequate (210 kg/ha), pH 6.4 slightly acidic."
    }
    resp = client.post("/api/knowledge/farmer-notes", json=note_payload, headers=alice["headers"])
    assert resp.status_code == 200
    note_data = resp.json()
    assert note_data["status"] == "success"
    note_id = note_data["note"]["id"]

    # 4. List farmer knowledge notes
    resp = client.get("/api/knowledge/farmer-notes", headers=alice["headers"])
    assert resp.status_code == 200
    list_data = resp.json()
    assert list_data["total_notes"] >= 1
    assert any(n["id"] == note_id for n in list_data["notes"])

    # 5. Query about soil test should retrieve the custom personal note
    soil_query = {"query": "What is my latest soil test result and nitrogen status?"}
    resp = client.post("/api/knowledge/query", json=soil_query, headers=alice["headers"])
    assert resp.status_code == 200
    soil_rag = resp.json()
    assert soil_rag["grounded"] is True
    assert any("custom_" in str(c.get("scheme_id")) or "Soil Test Certificate" in str(c.get("title")) for c in soil_rag["citations"])

    # 6. Delete farmer knowledge note
    del_resp = client.delete(f"/api/knowledge/farmer-notes/{note_id}", headers=alice["headers"])
    assert del_resp.status_code == 200


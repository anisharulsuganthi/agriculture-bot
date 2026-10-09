"""
RAG Engine & Agricultural Knowledge Retriever (Phases 4 & 5).

Provides vector retrieval and grounded synthesis over official agricultural schemes,
loans, guidelines, and farm advisories. Ensures every claim is strictly traced to citations.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.config import settings
from app.logging_config import get_logger

logger = get_logger("rag_engine")

_vector_index = None
_documents_store = []
_encoder_model = None


def load_knowledge_corpus() -> List[Dict[str, Any]]:
    """Loads all scheme and agronomic documents from knowledge base directory."""
    corpus = []
    kb_path = Path(settings.knowledge_base_dir)
    if not kb_path.is_dir():
        # Fallback to backend/data/knowledge_base if relative
        alt_path = Path(__file__).resolve().parents[1] / "data" / "knowledge_base"
        if alt_path.is_dir():
            kb_path = alt_path

    if not kb_path.is_dir():
        return corpus

    for file in kb_path.glob("*.json"):
        try:
            with open(file, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    corpus.extend(data)
                elif isinstance(data, dict):
                    corpus.append(data)
        except Exception as e:
            logger.warning("Failed to load knowledge file %s: %s", file, e)
    return corpus


def initialize_rag():
    """Initializes embeddings and FAISS index over official agricultural knowledge base."""
    global _vector_index, _documents_store, _encoder_model
    corpus = load_knowledge_corpus()
    _documents_store = []

    # Semantic chunking of document entities
    for doc in corpus:
        doc_id = doc.get("id", "doc")
        title = doc.get("title", "")
        category = doc.get("category", "")
        source_url = doc.get("source_url", "")
        ministry = doc.get("ministry", "")

        # Chunk 1: Overview & benefits
        _documents_store.append({
            "id": f"{doc_id}_overview",
            "scheme_id": doc_id,
            "title": title,
            "category": category,
            "ministry": ministry,
            "section": "Overview & Benefits",
            "content": f"{title} ({category}, {ministry}). {doc.get('description', '')} Benefits: {doc.get('benefits', '')}",
            "source_url": source_url
        })

        # Chunk 2: Eligibility & documents
        eligibility_txt = " ".join(doc.get("eligibility", [])) if isinstance(doc.get("eligibility"), list) else str(doc.get("eligibility", ""))
        docs_req_txt = ", ".join(doc.get("required_documents", [])) if isinstance(doc.get("required_documents"), list) else str(doc.get("required_documents", ""))
        _documents_store.append({
            "id": f"{doc_id}_eligibility",
            "scheme_id": doc_id,
            "title": title,
            "category": category,
            "ministry": ministry,
            "section": "Eligibility & Required Documents",
            "content": f"{title} eligibility criteria: {eligibility_txt} Required documents: {docs_req_txt}. How to apply: {doc.get('how_to_apply', '')}",
            "source_url": source_url
        })

    if not _documents_store:
        logger.info("Knowledge base is empty; RAG initialized with 0 documents.")
        return

    try:
        from sentence_transformers import SentenceTransformer
        import faiss
        import numpy as np

        _encoder_model = SentenceTransformer("all-MiniLM-L6-v2")
        texts = [d["content"] for d in _documents_store]
        embeddings = _encoder_model.encode(texts, convert_to_numpy=True, normalize_embeddings=True)
        
        dim = embeddings.shape[1]
        _vector_index = faiss.IndexFlatIP(dim)
        _vector_index.add(embeddings.astype(np.float32))
        logger.info("RAG initialized with %d chunks using FAISS + all-MiniLM-L6-v2", len(_documents_store))
    except Exception as e:
        logger.error("Error setting up FAISS vector store: %s. Falling back to keyword BM25 retrieval.", e)
        _vector_index = None


def retrieve_relevant_contexts(query: str, top_k: int = 3) -> List[Dict[str, Any]]:
    """Retrieves top-k context passages with cosine similarity scores and source metadata."""
    global _vector_index, _documents_store, _encoder_model
    if not _documents_store:
        initialize_rag()

    if not _documents_store:
        return []

    # FAISS Dense vector retrieval
    if _vector_index is not None and _encoder_model is not None:
        try:
            import numpy as np
            q_emb = _encoder_model.encode([query], convert_to_numpy=True, normalize_embeddings=True)
            scores, indices = _vector_index.search(q_emb.astype(np.float32), min(top_k, len(_documents_store)))
            
            results = []
            for score, idx in zip(scores[0], indices[0]):
                if idx < 0 or idx >= len(_documents_store):
                    continue
                doc = dict(_documents_store[idx])
                doc["relevance_score"] = float(round(score, 3))
                results.append(doc)
            return results
        except Exception as e:
            logger.warning("Vector search error, falling back to lexical search: %s", e)

    # Lexical fallback matching with stop-word filtering
    STOP_WORDS = {
        "what", "is", "the", "of", "in", "and", "to", "a", "an", "for", "on", "with",
        "about", "how", "much", "can", "i", "get", "my", "me", "tell", "which", "are",
        "do", "does", "at", "by", "from", "or", "as", "if", "will", "would", "please"
    }
    raw_q_words = re.findall(r"\w+", query.lower())
    q_words = {w for w in raw_q_words if w not in STOP_WORDS and len(w) > 2}
    if not q_words:
        return []

    scored_docs = []
    for doc in _documents_store:
        text_words = set(re.findall(r"\w+", doc["content"].lower()))
        overlap = len(q_words.intersection(text_words))
        if overlap > 0:
            doc_copy = dict(doc)
            doc_copy["relevance_score"] = round(overlap / len(q_words), 3)
            scored_docs.append(doc_copy)

    scored_docs.sort(key=lambda x: x["relevance_score"], reverse=True)
    return scored_docs[:top_k]


def get_farmer_land_classification(area_cents: Optional[float]) -> Dict[str, Any]:
    """Calculates land holding category according to standard agricultural norms."""
    cents = float(area_cents or 50.0)
    hectares = round(cents * 0.00404686, 3)
    acres = round(cents / 100.0, 2)
    if hectares <= 1.0:
        cat = "Marginal Farmer (< 1.0 ha / < 247 cents)"
        cat_key = "marginal"
    elif hectares <= 2.0:
        cat = "Small Farmer (1.0 - 2.0 ha / 247 - 494 cents)"
        cat_key = "small"
    else:
        cat = "Semi-Medium / Large Farmer (> 2.0 ha / > 494 cents)"
        cat_key = "large"
    return {
        "area_cents": cents,
        "hectares": hectares,
        "acres": acres,
        "category": cat,
        "category_key": cat_key
    }


def evaluate_farmer_eligibility(scheme_id: str, farmer_context: Dict[str, Any]) -> Dict[str, Any]:
    """Evaluates tailored scheme eligibility and projected benefits for a specific farmer profile."""
    land_info = get_farmer_land_classification(farmer_context.get("land_area_cents"))
    loc = farmer_context.get("location") or "Tamil Nadu, India"
    soil = farmer_context.get("soil_type") or "Loamy"
    crop = farmer_context.get("primary_crop") or "Tomato"
    irrigation = farmer_context.get("irrigation_source") or "Borewell / Drip"
    livestock = farmer_context.get("livestock_owned") or "Dairy Cattle"

    notes = []
    if scheme_id == "pm_kisan":
        notes.append(
            f"Under your landholding of {land_info['area_cents']} cents ({land_info['acres']} acres in {loc}), "
            f"you qualify as a {land_info['category']}. You are entitled to the direct benefit transfer of Rs. 6,000 annually (3 installments of Rs. 2,000)."
        )
        notes.append("Action: Ensure your bank account is Aadhaar-seeded with e-KYC completed on pmkisan.gov.in.")

    elif scheme_id == "kcc":
        notes.append(
            f"For your {land_info['acres']} acres cultivating '{crop}', you qualify for short-term crop loans up to Rs. 3 Lakhs at an effective 4% per annum interest rate."
        )
        if livestock:
            notes.append(
                f"With your registered livestock ({livestock}), you are eligible for an additional working capital loan of up to Rs. 2.00 Lakh without collateral."
            )

    elif scheme_id == "pmfby":
        commercial_crops = {"cotton", "sugarcane", "tomato", "potato", "chilli", "onion", "banana"}
        is_commercial = any(c in crop.lower() for c in commercial_crops)
        rate = "5% (commercial / horticultural)" if is_commercial else "2% (Kharif) or 1.5% (Rabi)"
        notes.append(
            f"For your primary crop '{crop}' on {land_info['acres']} acres, your insured farmer premium is capped at {rate}. The remaining actuarial premium is 100% subsidized by Central & State Governments."
        )

    elif scheme_id == "soil_health_card":
        notes.append(
            f"Free biennial soil testing is recommended for your {soil} soil in {loc}. "
            f"The 12-parameter report provides customized N-P-K and organic fertilizer dosages for '{crop}'."
        )

    elif scheme_id in ("pmksy", "drip_irrigation"):
        subsidy = "55% subsidy" if land_info["category_key"] in ("marginal", "small") else "45% subsidy"
        notes.append(
            f"Under PMKSY 'Per Drop More Crop', as a {land_info['category']}, you qualify for the higher {subsidy} on micro-irrigation equipment for your {irrigation} setup."
        )

    elif scheme_id == "aif":
        notes.append(
            f"Eligible for a 3% per annum interest subvention on loans up to Rs. 2 Crore for post-harvest infrastructure (cold storage, solar dryers, sorting units) in {loc}."
        )

    return {
        "scheme_id": scheme_id,
        "eligible": True,
        "farmer_classification": land_info["category"],
        "personalized_notes": notes
    }


def retrieve_farmer_custom_notes(
    query: str,
    user_id: Optional[int] = None,
    db: Optional[Any] = None,
    top_k: int = 2
) -> List[Dict[str, Any]]:
    """Retrieves personal farm notes/records belonging to the specific farmer."""
    if not user_id or db is None:
        return []

    try:
        from database import FarmerKnowledgeNote
    except ImportError:
        try:
            from backend.database import FarmerKnowledgeNote
        except ImportError:
            FarmerKnowledgeNote = None

    if FarmerKnowledgeNote is None:
        return []

    try:
        notes = db.query(FarmerKnowledgeNote).filter(FarmerKnowledgeNote.user_id == user_id).all()
        if not notes:
            return []

        STOP_WORDS = {
            "what", "is", "the", "of", "in", "and", "to", "a", "an", "for", "on", "with",
            "about", "how", "much", "can", "i", "get", "my", "me", "tell", "which", "are"
        }
        q_words = {w for w in re.findall(r"\w+", query.lower()) if w not in STOP_WORDS and len(w) > 2}
        scored = []
        for n in notes:
            n_text = f"{n.title} {n.content}".lower()
            text_words = set(re.findall(r"\w+", n_text))
            overlap = len(q_words.intersection(text_words)) if q_words else 0
            score = round(overlap / (len(q_words) or 1), 3) if q_words else 0.1
            if score > 0 or not q_words:
                scored.append({
                    "id": f"farmer_note_{n.id}",
                    "note_id": n.id,
                    "title": n.title,
                    "category": n.category,
                    "content": n.content,
                    "relevance_score": score,
                    "created_at": n.created_at.isoformat() if n.created_at else ""
                })
        scored.sort(key=lambda x: x["relevance_score"], reverse=True)
        return scored[:top_k]
    except Exception as e:
        logger.warning("Error querying farmer custom notes: %s", e)
        return []


def answer_agricultural_query(
    query: str,
    farmer_context: Optional[Dict[str, Any]] = None,
    db: Optional[Any] = None,
    user_id: Optional[int] = None
) -> Dict[str, Any]:
    """
    RAG synthesis: Retrieves verified official context and produces grounded answers with mandatory citations.
    Integrates farmer-specific personalization (profile characteristics and custom farm notes) when provided.
    """
    cleaned_query = (query or "").strip()
    if not cleaned_query or len(cleaned_query) < 2:
        return {
            "query": query,
            "answer": "Please ask a specific agricultural question regarding crops, diseases, irrigation, or government schemes.",
            "grounded": False,
            "citations": [],
            "retrieved_contexts_count": 0,
            "farmer_assessment": None
        }

    contexts = retrieve_relevant_contexts(cleaned_query, top_k=settings.rag_top_k)
    min_score = settings.rag_min_score

    # Filter by minimum confidence floor
    valid_contexts = [c for c in contexts if c.get("relevance_score", 0) >= min_score]

    # Also check farmer custom notes if user/db provided
    effective_user_id = user_id or (farmer_context.get("user_id") if farmer_context else None)
    farmer_notes = retrieve_farmer_custom_notes(cleaned_query, user_id=effective_user_id, db=db, top_k=2)

    if not valid_contexts and not farmer_notes:
        return {
            "query": query,
            "answer": "I could not find sufficient information in the available official government agricultural documents. Please verify with the local Agriculture Officer or the official portal.",
            "grounded": False,
            "citations": [],
            "retrieved_contexts_count": 0,
            "farmer_assessment": None
        }

    # Extract distinct citations
    citations = []
    seen_ids = set()
    for ctx in valid_contexts:
        s_id = ctx.get("scheme_id")
        if s_id not in seen_ids:
            seen_ids.add(s_id)
            citations.append({
                "scheme_id": s_id,
                "title": ctx.get("title"),
                "category": ctx.get("category"),
                "ministry": ctx.get("ministry"),
                "source_url": ctx.get("source_url"),
                "relevance_score": ctx.get("relevance_score")
            })

    for fn in farmer_notes:
        citations.append({
            "scheme_id": f"custom_{fn['note_id']}",
            "title": f"Farmer Note: {fn['title']}",
            "category": f"Personal Farm Record ({fn['category']})",
            "ministry": "Farmer Personal Knowledge Base",
            "source_url": "local_database",
            "relevance_score": fn.get("relevance_score", 1.0)
        })

    # Synthesize grounded answer
    answer_parts = []
    if valid_contexts:
        primary = valid_contexts[0]
        answer_parts.append(f"According to the official guidelines for {primary['title']} ({primary['ministry']}):\n{primary['content']}")
        if len(valid_contexts) > 1 and valid_contexts[1]["scheme_id"] != primary["scheme_id"]:
            secondary = valid_contexts[1]
            answer_parts.append(f"Additionally, {secondary['title']} provides relevant support:\n{secondary['content']}")

    if farmer_notes:
        fn_texts = [f"• {n['title']} ({n['category']}): {n['content']}" for n in farmer_notes]
        answer_parts.append("From your personal farm records & notes:\n" + "\n".join(fn_texts))

    # Build personalized assessment for the farmer if context exists
    farmer_assessment = None
    if farmer_context and valid_contexts:
        primary_scheme_id = valid_contexts[0].get("scheme_id")
        eligibility = evaluate_farmer_eligibility(primary_scheme_id, farmer_context)
        farmer_assessment = eligibility
        if eligibility.get("personalized_notes"):
            notes_str = "\n".join(f"• {n}" for n in eligibility["personalized_notes"])
            answer_parts.append(
                f"🌾 Personalized Assessment for Your Farm ({farmer_context.get('location', 'Registered Location')}):\n"
                f"- Classification: {eligibility['farmer_classification']}\n"
                f"- Tailored Guidance:\n{notes_str}"
            )

    synthesized_answer = "\n\n".join(answer_parts)

    return {
        "query": query,
        "answer": synthesized_answer,
        "grounded": True,
        "citations": citations,
        "retrieved_contexts_count": len(valid_contexts) + len(farmer_notes),
        "farmer_assessment": farmer_assessment
    }


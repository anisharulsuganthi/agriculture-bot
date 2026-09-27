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

    # Lexical fallback matching
    q_words = set(re.findall(r"\w+", query.lower()))
    scored_docs = []
    for doc in _documents_store:
        text_words = set(re.findall(r"\w+", doc["content"].lower()))
        overlap = len(q_words.intersection(text_words))
        if overlap > 0:
            doc_copy = dict(doc)
            doc_copy["relevance_score"] = round(overlap / (len(q_words) + 1), 3)
            scored_docs.append(doc_copy)

    scored_docs.sort(key=lambda x: x["relevance_score"], reverse=True)
    return scored_docs[:top_k]


def answer_agricultural_query(query: str, farmer_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    RAG synthesis: Retrieves verified context and produces grounded answers with mandatory citations.
    Includes hallucination guard when relevance threshold is not met.
    """
    cleaned_query = (query or "").strip()
    if not cleaned_query or len(cleaned_query) < 2:
        return {
            "query": query,
            "answer": "Please ask a specific agricultural question regarding crops, diseases, irrigation, or government schemes.",
            "grounded": False,
            "citations": [],
            "retrieved_contexts_count": 0
        }

    contexts = retrieve_relevant_contexts(cleaned_query, top_k=settings.rag_top_k)
    min_score = settings.rag_min_score

    # Filter by minimum confidence floor
    valid_contexts = [c for c in contexts if c.get("relevance_score", 0) >= min_score]

    if not valid_contexts:
        return {
            "query": query,
            "answer": "I could not find sufficient information in the available official government agricultural documents. Please verify with the local Agriculture Officer or the official portal.",
            "grounded": False,
            "citations": [],
            "retrieved_contexts_count": 0
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

    # Synthesize grounded answer from top verified passages
    primary = valid_contexts[0]
    answer_parts = [
        f"According to the official guidelines for {primary['title']} ({primary['ministry']}):",
        primary["content"]
    ]
    if len(valid_contexts) > 1 and valid_contexts[1]["scheme_id"] != primary["scheme_id"]:
        secondary = valid_contexts[1]
        answer_parts.append(f"Additionally, {secondary['title']} provides relevant support: {secondary['content']}")

    synthesized_answer = "\n\n".join(answer_parts)

    return {
        "query": query,
        "answer": synthesized_answer,
        "grounded": True,
        "citations": citations,
        "retrieved_contexts_count": len(valid_contexts)
    }

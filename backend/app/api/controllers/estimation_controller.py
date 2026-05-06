"""Estimation / RAG diagnostic controller.

Retained endpoints
------------------
POST /api/match-boq          — RAG single-item match (dev + QA)
POST /api/rag/diagnose       — BSR candidate scoring diagnostic (dev)
GET  /api/documents/         — Chroma vector store document browser (dev)

Removed (deprecated)
--------------------
POST /api/ingest-bsr             — Manual BSR PDF ingestion.  BSR data is now
                                   seeded automatically at startup; this
                                   manual trigger is no longer needed.
POST /api/estimate-project/stream/start  \
GET  /api/estimate-project/stream/{id}   — Legacy text-description estimation
                                           stream. Superseded by the wizard
                                           form route (form_controller.py) and
                                           the clarification chat route
                                           (clarification_controller.py).
"""
import json
from typing import Any

from chromadb.api.models.Collection import Collection
from fastapi import Depends, HTTPException
from pydantic import BaseModel, Field

from core.logging.logger import get_logger
from core.config.settings import settings
from infrastructure.data_layer.database.session import SessionLocal
from infrastructure.data_layer.vector_db.chroma_connection import get_chroma_collection_dependency
from services.rag_process.service import service
from services.rag_process.retriever import retrieve_candidates, extract_query_features, clean_boq_query
from services.rag_process.scorer import score_candidate

logger = get_logger(__name__)


# ─── Request models ───────────────────────────────────────────────────────────

class MatchRequest(BaseModel):
    boq_text: str = Field(..., min_length=3)


class DiagnoseRequest(BaseModel):
    descriptions: list[str] = Field(..., min_length=1)
    top_k: int = Field(default=5, ge=1, le=20)


# ─── Endpoint handlers ────────────────────────────────────────────────────────

def match_boq(payload: MatchRequest):
    """RAG single-item match — returns best BSR match for a BOQ description."""
    return service.match_boq_item(payload.boq_text)


def diagnose_bsr(payload: DiagnoseRequest):
    """Diagnostic: return top BSR candidates with raw scores for each BOQ description.

    POST /api/rag/diagnose
    Body: { "descriptions": ["..."], "top_k": 5 }
    Response: list of { description, cleaned_text, top_candidates: [...] }
    """
    results = []
    try:
        with SessionLocal() as db:
            for desc in payload.descriptions:
                query_features = extract_query_features(desc)
                cleaned_text = clean_boq_query(query_features.normalized_text)

                query_features_obj, candidates = retrieve_candidates(
                    boq_text=desc,
                    session=db,
                    vector_store=service._get_vector_store(),
                    embedder=service._get_embedder(),
                    top_k=payload.top_k,
                )

                SOFT = 0.30
                CONFIRM = settings.min_confidence_threshold
                scored_candidates = []
                for cand in candidates:
                    bsr_item = cand["bsr_item"]
                    scores = score_candidate(query_features_obj, bsr_item, cand["vector_score"])
                    fs = scores["final_score"]
                    if fs < SOFT:
                        mt = "no_match"
                    elif fs < CONFIRM:
                        mt = "soft_match"
                    else:
                        mt = "confirmed"
                    scored_candidates.append({
                        "item_no": bsr_item.item_no,
                        "bsr_description": bsr_item.description,
                        "unit": bsr_item.unit,
                        "rate": bsr_item.rate,
                        "vector_score": scores["vector_score"],
                        "keyword_score": scores["keyword_score"],
                        "final_score": scores["final_score"],
                        "match_type": mt,
                        "matched_fields": scores["matched_fields"],
                    })

                scored_candidates.sort(key=lambda x: x["final_score"], reverse=True)
                results.append({
                    "description": desc,
                    "cleaned_text": cleaned_text,
                    "detected_work_type": query_features.work_type,
                    "detected_material": query_features.material,
                    "top_candidates": scored_candidates,
                })
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return {"count": len(results), "results": results}


def get_documents(
    collection: Collection = Depends(get_chroma_collection_dependency),
):
    """Browse documents stored in the Chroma vector store (dev utility)."""
    try:
        total_count = collection.count()
        results = collection.get(limit=50, include=["documents", "metadatas"])
        ids = results.get("ids") or []
        documents = results.get("documents") or []
        metadatas = results.get("metadatas") or []
        items = [
            {"id": doc_id, "document": document, "metadata": metadata}
            for doc_id, document, metadata in zip(ids, documents, metadatas)
        ]
        return {"count": len(items), "total_count": total_count, "items": items}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

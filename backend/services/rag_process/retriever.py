import re
from dataclasses import dataclass

from sqlalchemy.orm import Session

from services.rag_process.db import get_bsr_items_by_ids
from services.rag_process.embeddings import EmbeddingProvider
from infrastructure.data_layer.vector_db.vector_store import ChromaBSRVectorStore


NOISE_WORDS = {
    "the",
    "and",
    "for",
    "with",
    "of",
    "to",
    "in",
    "including",
    "providing",
    "as",
    "per",
}

WORK_TYPES = ["excavation", "concrete", "masonry", "plaster", "reinforcement", "flooring"]
METHODS = ["manual", "machine", "ready-mix"]
MATERIAL_HINTS = ["ordinary soil", "hard soil", "rock", "m20", "m25", "brick", "sand"]


@dataclass(frozen=True)
class QueryFeatures:
    normalized_text: str
    tokens: list[str]
    work_type: str | None
    material: str | None
    method: str | None
    constraints: list[str]


def normalize_query(text: str) -> str:
    lowered = text.lower()
    lowered = re.sub(r"[^a-z0-9\s\-./]", " ", lowered)
    lowered = re.sub(r"\s+", " ", lowered).strip()
    return lowered


def extract_query_features(text: str) -> QueryFeatures:
    normalized = normalize_query(text)
    tokens = [token for token in normalized.split() if token not in NOISE_WORDS]

    work_type = next((label for label in WORK_TYPES if label in normalized), None)
    method = next((label for label in METHODS if label in normalized), None)
    material = next((label for label in MATERIAL_HINTS if label in normalized), None)

    constraints: list[str] = []
    depth_matches = re.findall(r"depth\s*(?:up to|of|exceeding)?\s*([\d.]+\s*(?:m|mm|cm))", normalized)
    constraints.extend([f"depth:{m}" for m in depth_matches])

    size_matches = re.findall(r"(\d+\s*[x×]\s*\d+\s*(?:mm|cm|m)?)", normalized)
    constraints.extend([f"size:{m}" for m in size_matches])

    floor_matches = re.findall(r"(ground floor|first floor|basement|upper floor)", normalized)
    constraints.extend([f"floor:{m}" for m in floor_matches])

    return QueryFeatures(
        normalized_text=normalized,
        tokens=tokens,
        work_type=work_type,
        material=material,
        method=method,
        constraints=constraints,
    )


def retrieve_candidates(
    boq_text: str,
    session: Session,
    vector_store: ChromaBSRVectorStore,
    embedder: EmbeddingProvider,
    top_k: int = 5,
) -> tuple[QueryFeatures, list[dict]]:
    query_features = extract_query_features(boq_text)
    query_embedding = embedder.embed_one(query_features.normalized_text)

    where = None
    if query_features.work_type:
        where = {"work_type": query_features.work_type}

    vector_hits = vector_store.query(query_embedding, top_k=top_k, where=where)
    if not vector_hits and where is not None:
        vector_hits = vector_store.query(query_embedding, top_k=top_k, where=None)

    ids = [hit["postgres_id"] for hit in vector_hits]
    items = get_bsr_items_by_ids(session, ids)
    item_map = {item.id: item for item in items}

    candidates: list[dict] = []
    for hit in vector_hits:
        bsr_item = item_map.get(hit["postgres_id"])
        if not bsr_item:
            continue
        candidates.append({"bsr_item": bsr_item, "vector_score": float(hit["vector_score"])})

    return query_features, candidates

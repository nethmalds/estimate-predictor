from pathlib import Path

from ai.rag.db import init_db, upsert_bsr_items
from ai.rag.embeddings import EmbeddingProvider
from ai.rag.pdf_parser import parse_bsr_pdf
from ai.rag.retriever import retrieve_candidates
from ai.rag.scorer import score_candidate
from core.config.settings import settings
from data_layer.vector_db.vector_store import ChromaBSRVectorStore
from data_layer.database.session import SessionLocal


class BOQMatcherService:
    def __init__(self):
        self.embedder: EmbeddingProvider | None = None
        self.vector_store: ChromaBSRVectorStore | None = None

    def _get_embedder(self) -> EmbeddingProvider:
        if self.embedder is None:
            self.embedder = EmbeddingProvider()
        return self.embedder

    def _get_vector_store(self) -> ChromaBSRVectorStore:
        if self.vector_store is None:
            self.vector_store = ChromaBSRVectorStore()
        return self.vector_store

    def bootstrap(self) -> None:
        init_db()

    def ingest_bsr_pdf(self, pdf_path: str) -> dict:
        parsed_items = parse_bsr_pdf(pdf_path)
        if not parsed_items:
            return {"ingested": 0, "message": "No rows parsed from PDF."}

        with SessionLocal() as db:
            db_items = upsert_bsr_items(db, parsed_items)

        vector_records = []
        embedding_texts = []
        for item in db_items:
            vector_records.append(
                {
                    "postgres_id": item.id,
                    "item_no": item.item_no,
                    "category": item.category,
                    "work_type": item.work_type,
                }
            )
            embedding_texts.append(
                self._get_embedder().build_embedding_text(item.item_no, item.description, item.category)
            )

        embeddings = self._get_embedder().embed_many(embedding_texts)
        self._get_vector_store().upsert(vector_records, embeddings)

        return {"ingested": len(db_items), "source": str(Path(pdf_path).resolve())}

    def match_boq_item(self, boq_text: str) -> dict:
        with SessionLocal() as db:
            query_features, candidates = retrieve_candidates(
                boq_text=boq_text,
                session=db,
                vector_store=self._get_vector_store(),
                embedder=self._get_embedder(),
                top_k=settings.retrieval_top_k,
            )

            if not candidates:
                return {"item_no": "NO_MATCH", "confidence": 0.0}

            scored = []
            for candidate in candidates:
                item = candidate["bsr_item"]
                component_scores = score_candidate(query_features, item, candidate["vector_score"])
                scored.append((item, component_scores))

            best_item, best_scores = max(scored, key=lambda pair: pair[1]["final_score"])

            if best_scores["final_score"] < settings.min_confidence_threshold:
                return {"item_no": "NO_MATCH", "confidence": 0.0}

            return {
                "item_no": best_item.item_no,
                "description": best_item.description,
                "unit": best_item.unit,
                "rate": best_item.rate,
                "confidence": best_scores["final_score"],
                "match_details": {
                    "vector_score": best_scores["vector_score"],
                    "keyword_score": best_scores["keyword_score"],
                    "matched_fields": best_scores["matched_fields"],
                },
            }



service = BOQMatcherService()

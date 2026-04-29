import threading
from pathlib import Path
from core.logging.logger import get_logger

logger = get_logger(__name__)

from services.rag_process.db import init_db, upsert_bsr_items
from services.rag_process.embeddings import EmbeddingProvider
from services.rag_process.pdf_parser import parse_bsr_pdf
from services.rag_process.retriever import retrieve_candidates
from services.rag_process.scorer import score_candidate
from core.config.settings import settings
from infrastructure.data_layer.vector_db.vector_store import ChromaBSRVectorStore
from infrastructure.data_layer.database.session import SessionLocal
from infrastructure.data_layer.database.models.bsr_item import BSRItem


class BOQMatcherService:
    def __init__(self):
        self._lock = threading.Lock()  # R8: guards lazy init of embedder + vector_store
        self.embedder: EmbeddingProvider | None = None
        self.vector_store: ChromaBSRVectorStore | None = None

    def _get_embedder(self) -> EmbeddingProvider:
        if self.embedder is None:
            with self._lock:
                if self.embedder is None:  # double-checked locking
                    self.embedder = EmbeddingProvider()
        return self.embedder

    def _get_vector_store(self) -> ChromaBSRVectorStore:
        if self.vector_store is None:
            with self._lock:
                if self.vector_store is None:  # double-checked locking
                    self.vector_store = ChromaBSRVectorStore()
        return self.vector_store

    def bootstrap(self) -> None:
        init_db()
        with SessionLocal() as db:
            count = db.query(BSRItem).count()
            if count == 0:
                logger.info("Database is empty. Auto-ingesting BSR PDF...")
                pdf_path = Path(__file__).resolve().parents[2] / "infrastructure" / "data_layer" / "storage" / "bsr_wp_2025.pdf"
                if pdf_path.exists():
                    self.ingest_bsr_pdf(str(pdf_path))
                else:
                    logger.warning(f"Auto-ingest skipped: PDF not found at {pdf_path}")

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
                return {"item_no": "NO_MATCH", "confidence": 0.0, "match_type": "no_match", "needs_rate_review": True}

            scored = []
            for candidate in candidates:
                item = candidate["bsr_item"]
                component_scores = score_candidate(query_features, item, candidate["vector_score"])
                scored.append((item, component_scores))

            best_item, best_scores = max(scored, key=lambda pair: pair[1]["final_score"])
            final_score = best_scores["final_score"]

            # --- Three-tier confidence system ---
            # < SOFT_THRESHOLD  → no usable match at all
            SOFT_THRESHOLD = 0.30
            CONFIRM_THRESHOLD = settings.min_confidence_threshold  # 0.45

            if final_score < SOFT_THRESHOLD:
                return {"item_no": "NO_MATCH", "confidence": 0.0, "match_type": "no_match", "needs_rate_review": True}

            # Soft match: score in [SOFT_THRESHOLD, CONFIRM_THRESHOLD)
            match_type = "confirmed" if final_score >= CONFIRM_THRESHOLD else "soft_match"
            needs_rate_review = match_type == "soft_match"

            return {
                "item_no": best_item.item_no,
                "description": best_item.description,
                "unit": best_item.unit,
                "rate": best_item.rate,
                "confidence": final_score,
                "match_type": match_type,
                "needs_rate_review": needs_rate_review,
                "match_details": {
                    "vector_score": best_scores["vector_score"],
                    "keyword_score": best_scores["keyword_score"],
                    "matched_fields": best_scores["matched_fields"],
                },
            }


service = BOQMatcherService()

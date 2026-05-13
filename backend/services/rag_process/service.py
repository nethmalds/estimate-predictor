import logging
import threading
from pathlib import Path


from services.rag_process.db import upsert_bsr_items, init_db
from services.rag_process.embeddings import EmbeddingProvider
from services.rag_process.pdf_parser import parse_bsr_pdf
from services.rag_process.retriever import retrieve_candidates, extract_query_features, clean_boq_query
from services.rag_process.scorer import score_candidate
from services.rag_process.matcher import match_boq_items_batch as _match_boq_items_batch
from core.config.settings import settings
from infrastructure.data_layer.vector_db.vector_store import ChromaBSRVectorStore
from infrastructure.data_layer.database.session import SessionLocal
from infrastructure.data_layer.database.models.bsr_item import BSRItem


logger = logging.getLogger(__name__)


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

    def bootstrap(self) -> dict:
        pdf_path = Path(__file__).resolve().parents[2] / "infrastructure" / "data_layer" / "storage" / "bsr_wp_2025.pdf"

        with SessionLocal() as db:
            postgres_count = db.query(BSRItem).count()

        chroma_count = self._get_vector_store().collection.count()
        logger.info(
            "BSR bootstrap check: postgres_rows=%d chroma_vectors=%d collection=%s",
            postgres_count,
            chroma_count,
            settings.chroma_collection,
        )

        if postgres_count > 0 and chroma_count > 0:
            logger.info("BSR bootstrap skipped: Postgres and Chroma already contain data.")
            return {
                "ingested": 0,
                "source": str(pdf_path.resolve()),
                "postgres_rows": postgres_count,
                "chroma_vectors": chroma_count,
                "skipped": True,
            }

        if not pdf_path.exists():
            logger.warning("BSR bootstrap skipped: bundled PDF not found at %s", pdf_path)
            return {
                "ingested": 0,
                "message": "Bundled BSR PDF not found.",
                "source": str(pdf_path.resolve()),
                "postgres_rows": postgres_count,
                "chroma_vectors": chroma_count,
                "skipped": True,
            }

        if postgres_count > 0 and chroma_count == 0:
            logger.info("BSR bootstrap restoring missing Chroma vectors from bundled PDF.")
        elif postgres_count == 0:
            logger.info("BSR bootstrap ingesting bundled PDF because Postgres is empty.")

        result = self.ingest_bsr_pdf(str(pdf_path))
        logger.info(
            "BSR bootstrap completed: ingested=%s source=%s",
            result.get("ingested", 0),
            result.get("source", str(pdf_path.resolve())),
        )
        return result

    def ingest_bsr_pdf(self, pdf_path: str) -> dict:
        parsed_items = parse_bsr_pdf(pdf_path)
        if not parsed_items:
            return {"ingested": 0, "message": "No rows parsed from PDF."}

        with SessionLocal() as db:
            db_items = upsert_bsr_items(db, parsed_items)
            db.commit()
            for item in db_items:
                db.refresh(item)

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

    def match_boq_items_batch(self, items: list[dict]) -> list[dict]:
        """Batch-match a list of BOQ items against BSR, skipping contractual ones."""
        return _match_boq_items_batch(items, self.match_boq_item)


service = BOQMatcherService()

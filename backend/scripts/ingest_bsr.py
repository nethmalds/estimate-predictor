"""BSR PDF ingestion script.

Parses the bundled BSR Work Payments 2025 PDF, persists items to Postgres,
and upserts embeddings into ChromaDB.

Usage:
    python scripts/ingest_bsr.py                        # use bundled PDF
    python scripts/ingest_bsr.py /path/to/custom.pdf    # custom path

The script is idempotent — re-running it upserts rather than duplicating rows.
It skips ingestion entirely if both Postgres and Chroma already have data,
unless --force is passed.

Flags:
    --force   Re-ingest even if data already exists (full upsert).
    --help    Show this message and exit.
"""

import argparse
import sys
from pathlib import Path

# Ensure backend root is on sys.path when run directly
ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("ingest_bsr")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Ingest BSR PDF into Postgres + ChromaDB.",
        add_help=True,
    )
    parser.add_argument(
        "pdf_path",
        nargs="?",
        default=None,
        help="Path to the BSR PDF (default: infrastructure/data_layer/storage/bsr_wp_2025.pdf)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-ingest even if data already exists.",
    )
    args = parser.parse_args()

    # Resolve PDF path
    if args.pdf_path:
        pdf_path = Path(args.pdf_path).resolve()
    else:
        pdf_path = ROOT_DIR / "infrastructure" / "data_layer" / "storage" / "bsr_wp_2025.pdf"

    if not pdf_path.exists():
        logger.error("BSR PDF not found: %s", pdf_path)
        logger.error(
            "Place bsr_wp_2025.pdf in backend/infrastructure/data_layer/storage/ "
            "or pass a custom path as an argument."
        )
        return 1

    # Late import — keeps startup fast when --help is used
    from infrastructure.data_layer.database.models.bsr_item import BSRItem
    from infrastructure.data_layer.database.session import SessionLocal
    from infrastructure.data_layer.vector_db.vector_store import ChromaBSRVectorStore
    from services.rag_process.service import BOQMatcherService

    # Check existing data
    with SessionLocal() as db:
        postgres_count = db.query(BSRItem).count()

    vector_store = ChromaBSRVectorStore()
    chroma_count = vector_store.collection.count()

    logger.info(
        "Current state — Postgres: %d rows | Chroma: %d vectors",
        postgres_count,
        chroma_count,
    )

    if postgres_count > 0 and chroma_count > 0 and not args.force:
        logger.info(
            "Both stores already have data. Skipping ingestion. "
            "Pass --force to re-ingest."
        )
        return 0

    if args.force:
        logger.info("--force flag set — re-ingesting regardless of existing data.")

    logger.info("Starting ingestion from: %s", pdf_path)
    svc = BOQMatcherService()
    result = svc.ingest_bsr_pdf(str(pdf_path))

    ingested = result.get("ingested", 0)
    if ingested == 0:
        logger.warning("No items were ingested. Check the PDF format.")
        return 1

    logger.info("Done — ingested %d items.", ingested)
    return 0


if __name__ == "__main__":
    sys.exit(main())

# Construction Cost Estimation RAG (BOQ -> BSR)

Deterministic, explainable RAG pipeline that maps BOQ item text to official BSR items using:
- PostgreSQL for structured records
- Chroma for semantic retrieval
- Rule-based scoring for final rank (no LLM in retrieval)

## Architecture

- `infrastructure/ai/rag/pdf_parser.py`: Parse BSR PDF table rows to structured records.
- `infrastructure/ai/rag/db.py`: PostgreSQL data access and upsert logic.
- `infrastructure/ai/rag/embeddings.py`: Embedding generation (`item_no + description + category`).
- `infrastructure/data_layer/vector_db/vector_store.py`: Chroma persistence and candidate retrieval.
- `infrastructure/data_layer/vector_db/chroma_connection.py`: Shared Chroma client/collection dependencies for FastAPI.
- `infrastructure/ai/rag/retriever.py`: Query normalization, token extraction, and top-k retrieval.
- `infrastructure/ai/rag/scorer.py`: Deterministic weighted scoring.
- `infrastructure/ai/rag/service.py`: End-to-end orchestration.
- `app/api/controllers/estimation_controller.py`: FastAPI endpoints.

## Database Schema

Table: `bsr_items`
- `id` (PK)
- `item_no` (unique)
- `description`
- `unit`
- `rate`
- `category`
- optional: `work_type`, `material_type`, `method`, `constraints`, `metadata` (JSONB)

Indexes:
- `ix_bsr_items_item_no`
- `ix_bsr_items_category`
- `ix_bsr_items_work_type`

## Matching Logic

1. Normalize BOQ query and remove noise terms.
2. Extract deterministic features:
   - `work_type`
   - `material`
   - `method`
   - `constraints` (depth/size/floor)
3. Retrieve top-k from Chroma (default 5).
4. Fetch full records from PostgreSQL by candidate IDs.
5. Score each candidate:
   - Vector similarity weight: `0.65`
   - Keyword/rule weight: `0.35`

Rule points:
- `+3` exact material match
- `+2` work type match
- `+2` method match
- `+1` constraints match
- `+1` partial token overlap

`final_score = 0.65 * vector_score + 0.35 * keyword_score_normalized`

If `final_score < MIN_CONFIDENCE_THRESHOLD` -> `NO_MATCH`

## API

### `POST /ingest-bsr`

```json
{
  "pdf_path": "D:/path/to/bsr_wp_2025.pdf"
}
```

### `POST /match-boq`

```json
{
  "boq_text": "Excavation in ordinary soil up to depth 1.5m by manual means"
}
```

Response format:

```json
{
  "item_no": "3.1.2",
  "description": "Excavation in ordinary soil ...",
  "unit": "cum",
  "rate": 350.0,
  "confidence": 0.83,
  "match_details": {
    "vector_score": 0.79,
    "keyword_score": 0.9,
    "matched_fields": ["material:ordinary soil", "work_type:excavation", "method:manual", "constraints"]
  }
}
```

Failure response:

```json
{
  "item_no": "NO_MATCH",
  "confidence": 0.0
}

### `POST /estimate-project`

```json
{
  "description": "Two-storey residential building with 6 rooms.",
  "floorplan_image_url": "https://example.com/floorplan.png"
}
```

If required parameters are missing, the response includes `status: "needs_clarification"` and a list of questions.
```

### `POST /api/documents/`

Batch upload documents to Chroma collection using FastAPI dependency injection.

```json
{
  "ids": ["doc-1", "doc-2"],
  "documents": ["Excavation in ordinary soil", "PCC 1:4:8 in foundation"],
  "metadatas": [
    {"source": "manual", "category": "earthwork"},
    {"source": "manual", "category": "concrete"}
  ]
}
```

## Run

1. Install dependencies:
   - `pip install -r requirements.txt`
2. Start PostgreSQL + Chroma containers:
  - `docker compose -f docker/docker-compose.yml --env-file .env.local up -d postgres_db chroma_db`
3. Ensure env is configured in `.env.local` (see RAG Configuration below).
4. Apply DB migrations (creates `bsr_items` table):
   - `alembic upgrade head`
5. Start API:
  - `uvicorn app.api.server:app --reload`
6. Run manual PDF ingestion (required before retrieval):
  - `python scripts/manual_ingest.py` (uses `data_layer/storage/bsr_wp_2025.pdf`)
  - or `python scripts/manual_ingest.py "D:/path/to/other_bsr.pdf"`
7. Match BOQ items using `/match-boq`

## Manual Ingestion

BSR PDF ingestion into PostgreSQL + Chroma is run manually via script.

- Script: `scripts/manual_ingest.py`
- Under the hood: `python -m infrastructure.ai.rag.manual_ingest --pdf-path <path>`

This keeps ingestion decoupled from API runtime, and retrieval only runs when matching endpoints are called.

## Centralized DB Config

All DB and retrieval configuration lives in `core/config/settings.py`.

## RAG Configuration

Use these variables for RAG (loaded from `.env.local`):

- `CHROMA_COLLECTION`
- `CHROMA_HOST`
- `CHROMA_PORT`
- `CHROMA_SSL`
- `CHROMA_API_KEY`
- `EMBEDDING_MODEL`
- `RETRIEVAL_TOP_K`

Development defaults:

- `CHROMA_HOST=localhost`
- `CHROMA_PORT=8080`
- `MIN_CONFIDENCE_THRESHOLD`

## LLM Configuration

The Ollama client uses `.env.local` variables:

- `OLLAMA_API_KEY`
- `OLLAMA_HOST`
- `OLLAMA_MODEL` (default: `glm-5:cloud`)

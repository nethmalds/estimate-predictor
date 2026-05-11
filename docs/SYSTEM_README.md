# Construction Cost Estimation System — Full System Overview

> **Purpose of this document:** Explain the end-to-end architecture, data flow, and every processing stage of the system, and call out what works, what is a placeholder, and what needs improvement.

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Repository Structure](#2-repository-structure)
3. [Tech Stack & Infrastructure](#3-tech-stack--infrastructure)
4. [Full Data Flow](#4-full-data-flow)
5. [Stage-by-Stage Pipeline Breakdown](#5-stage-by-stage-pipeline-breakdown)
   - [Stage 0 — Clarification (Interactive)](#stage-0--clarification-interactive)
   - [Stage 1 — Project Info Extraction](#stage-1--project-info-extraction)
   - [Stage 2 — Floorplan Processing (Optional)](#stage-2--floorplan-processing-optional)
   - [Stage 3 — BOQ Item Generation (3-Stage)](#stage-3--boq-item-generation-3-stage)
   - [Stage 4 — RAG / BSR Matching](#stage-4--rag--bsr-matching)
   - [Stage 5 — Quantity Take-Off Engine](#stage-5--quantity-take-off-engine)
   - [Stage 6 — Validation](#stage-6--validation)
   - [Stage 7 — Cost Calculation](#stage-7--cost-calculation)
   - [Stage 8 — Transparency & Confidence](#stage-8--transparency--confidence)
   - [Stage 9 — Reporting](#stage-9--reporting)
6. [API Endpoints](#6-api-endpoints)
7. [Frontend](#7-frontend)
8. [ML Models](#8-ml-models)
9. [RAG System Detail](#9-rag-system-detail)
10. [Known Issues & Areas That Need Improvement](#10-known-issues--areas-that-need-improvement)

---

## 1. System Overview

The system is an AI-assisted **construction cost estimation tool**. A user describes a building project (or uploads a floorplan image), and the system produces a **Bill of Quantities (BOQ)** with matched **Bill of Schedule of Rates (BSR)** codes, computed quantities, and a total cost estimate.

```
User Description + Optional Floorplan Image
              │
              ▼
   ┌─────────────────────┐
   │  Clarification Flow │  ← asks follow-up questions if info is missing
   └──────────┬──────────┘
              │ project_info dict
              ▼
   ┌──────────────────────────────────────────────────────┐
   │              11-Stage Estimation Pipeline             │
   │  1. Floorplan download + cache                       │
   │  2. CV pipeline (YOLO + OCR) → geometry              │
   │  3. Item Predictor (Random Forest) → candidate items │
   │  4. LLM Baseline BOQ                                 │
   │  5. LLM Gap-Fill                                     │
   │  6. RAG → BSR code / unit / rate                     │
   │  7. Quantity Take-Off (geometry rules / ML)          │
   │  8. Validation                                       │
   │  9. Cost Calculation (qty × rate + contingencies)    │
   │ 10. Transparency & Confidence Score                  │
   │ 11. Reporting                                        │
   └──────────────────────────────────────────────────────┘
              │
              ▼
   Structured cost estimate (JSON / future: Excel / PDF)
```

---

## 2. Repository Structure

```
codebase/
├── backend/                     # Python FastAPI application
│   ├── app/
│   │   ├── api/
│   │   │   ├── server.py            # FastAPI app factory + startup
│   │   │   ├── controllers/         # Request handlers (estimation, clarification, project)
│   │   │   ├── middleware/          # Request logging
│   │   │   ├── routes/router.py     # All API routes registered here
│   │   │   ├── schemas/             # (empty — schemas are inline in controllers)
│   │   │   └── state/session.py     # In-memory session store (SSE streaming)
│   │   └── worker/tasks/            # Celery task stubs (not yet wired)
│   ├── application/
│   │   └── pipelines/
│   │       ├── estimation_pipeline.py  # Main 11-stage orchestrator
│   │       └── floorplan_pipeline.py   # Thin wrapper around floorplan service
│   ├── core/
│   │   ├── config/settings.py       # All env-var config (PostgreSQL, Chroma, LLM, etc.)
│   │   ├── exceptions/error_handlers.py
│   │   └── logging/logger.py        # Three-file logging setup
│   ├── infrastructure/
│   │   ├── ai/models/
│   │   │   ├── item_pred/           # item_predictor.joblib (Random Forest)
│   │   │   ├── quantity_pred/       # quantity_predictor.joblib (regression)
│   │   │   └── object_detect/       # YOLO model weights (new_best.pt)
│   │   ├── data_layer/
│   │   │   ├── database/            # SQLAlchemy + PostgreSQL (BSR items, sessions)
│   │   │   ├── storage/             # bsr_wp_2025.pdf BSR source document
│   │   │   └── vector_db/           # ChromaDB client + vector store
│   │   └── integrations/
│   │       ├── openrouter_client.py # OpenAI-compatible LLM gateway
│   │       └── prompt_templates/    # .txt prompt templates used by LLM clients
│   ├── services/                    # Domain service modules (each has a public facade)
│   │   ├── clarification_process/   # LLM project-info extraction + clarification Q&A
│   │   ├── floorplan_process/       # OCR + YOLO geometry extraction
│   │   ├── item_gen_process/        # 3-stage BOQ item generation
│   │   ├── pricing_process/         # Cost calculation (rate × qty)
│   │   ├── quantity_gen_process/    # Quantity Take-Off (branched: geometry vs ML)
│   │   ├── rag_process/             # RAG pipeline (BSR ingest + BOQ matching)
│   │   ├── reporting_process/       # Report assembly (Excel/PDF stubs)
│   │   └── validation/              # Quantity validation + confidence scoring
│   ├── docker/docker-compose.yml    # PostgreSQL + ChromaDB containers
│   └── requirements.txt
└── frontend/                    # Next.js chat interface
    └── src/
        ├── app/page.tsx             # Main chat UI
        ├── services/estimation.ts   # API client (fetch + SSE)
        └── lib/uploadthing.ts       # File upload (floorplan images)
```

---

## 3. Tech Stack & Infrastructure

| Component | Technology |
|---|---|
| Backend API | Python 3.11+, FastAPI, Uvicorn |
| Frontend | Next.js (React), TypeScript, Tailwind CSS |
| Relational DB | PostgreSQL 16 (BSR items, structured data) |
| Vector DB | ChromaDB 0.5.5 (BSR embeddings for semantic search) |
| Embeddings | `sentence-transformers` (model configured via `EMBEDDING_MODEL` env var) |
| LLM Gateway | OpenRouter API (`openai` SDK, model: `openai/gpt-oss-120b:free` default) |
| ML — Item Prediction | scikit-learn `MultiOutputClassifier` (Random Forest), joblib artifact |
| ML — Quantity Prediction | scikit-learn regression model (global + per-item), joblib artifact |
| CV — Floorplan | YOLO (`ultralytics`) with `new_best.pt`, Tesseract OCR (`pytesseract`) |
| File Uploads | UploadThing (frontend → CDN URL passed to backend) |
| Real-time streaming | Server-Sent Events (SSE) via `asyncio.Queue` |
| Containerization | Docker Compose (DB services only; API runs locally) |
| ORM / Migrations | SQLAlchemy 2.0, Alembic |
| PDF Parsing | `pdfplumber` (BSR PDF ingestion) |

---

## 4. Full Data Flow

### Path A — With Clarification (Interactive Chat)

```
POST /api/estimate-project/clarification/start
  { description, floorplan_image_url? }
         │
         ▼
  extract_project_info()          ← LLM call #1
  find_missing_fields()           ← rule check (7 fields required)
         │
    ┌────┴──────┐
    │ Missing?  │
    └────┬──────┘
    yes  │  no
         │         ──────────────────────────────►  run pipeline immediately
         ▼
  queue first question → SSE stream → client receives "question" event
         │
POST /api/estimate-project/clarification/{session_id}/answer
  { answer }
         │
         ▼
  merge answer into session state
  ask next question (if any) ──► repeat
         │
  all answered
         │
  extract_project_info_with_clarifications()  ← LLM call #2
         │
  run_estimation_pipeline_from_project_info()
         │
  results streamed via SSE → client receives "result" event
```

### Path B — Direct Estimation Stream

```
POST /api/estimate-project/stream/start
  { description, floorplan_image_url? }
         │
         ▼
  run_estimation_pipeline() → streams progress events
```

### SSE Events emitted to frontend

| Event | Meaning |
|---|---|
| `question` | Clarification question for user |
| `progress` | A pipeline stage started / completed / failed |
| `result` | Final estimation payload |
| `info` | Informational message |
| `error` | Fatal error |

---

## 5. Stage-by-Stage Pipeline Breakdown

### Stage 0 — Clarification (Interactive)

**File:** `services/clarification_process/`

**What it does:**
- LLM extracts structured `project_info` from free-text description.
- Rule-based check identifies which of the **7 required fields** are missing:
  - Root: `floors`
  - Parameters: `bedrooms`, `bathrooms`, `built_up_area`, `finish_level`, `roof_type`, `ceiling_type`
- Pre-written questions are presented to the user one at a time via SSE.
- Answers are merged back into `project_info` before the pipeline runs.

**Output:** Complete `project_info` dict:
```json
{
  "building_type": "residential",
  "floors": 2,
  "spaces": ["living room", "kitchen"],
  "parameters": {
    "bedrooms": 3,
    "bathrooms": 2,
    "built_up_area": "1800 sq ft",
    "finish_level": "standard",
    "roof_type": "flat concrete slab",
    "ceiling_type": "gypsum"
  }
}
```

---

### Stage 1 — Project Info Extraction

**File:** `services/clarification_process/llm_client.py`

**What it does:**
- Calls the LLM via OpenRouter with prompt template `extract_project_info.txt`.
- Also calls `check_requirements.txt` to double-check completeness.
- JSON response is parsed and normalised.

**LLM Calls:** 1–2 (info extraction + requirements check)

---

### Stage 2 — Floorplan Processing (Optional)

**Files:** `services/floorplan_process/`, `application/pipelines/floorplan_pipeline.py`

**What it does:**
1. Downloads and caches the floorplan image from its CDN URL.
2. Runs YOLO (`new_best.pt`) to detect:
   - Doors (class 0)
   - Windows (class 1)
   - Room zones (class 2)
3. Runs Tesseract OCR to extract dimension text (e.g., "3500 mm").
4. Computes a **geometry dict**:
   - `total_floor_area_m2`: sum of YOLO zone areas
   - `perimeter_m`: approximated as `4 × √(total_area)` (⚠️ see issues)
   - `wall_length_m`: perimeter + estimated internal walls
   - `opening_count`: doors + windows
   - `room_count`
   - `rooms`: list of `{label, area_m2}`

**Output:** `floorplan_geometry` dict (or `None` if no image provided / processing fails)

---

### Stage 3 — BOQ Item Generation (3-Stage)

**File:** `services/item_gen_process/boq_builder.py`

Three sub-stages run in sequence:

#### Sub-stage 3a — Item Predictor (ML)
- **Model:** Random Forest `MultiOutputClassifier` (`item_predictor.joblib`)
- Encodes 6 features: `Total_Area`, `Floors`, `Budget_enc`, `Project_Type_enc`, `Roof_Type_enc`, `Ceiling_Type_enc`
- Predicts which **work categories** are required, then maps categories → item description strings from `cat_to_items` lookup.
- Output: `list[str]` — candidate item descriptions (hints for the LLM).

#### Sub-stage 3b — LLM Baseline BOQ
- **Prompt:** `generate_baseline_boq.txt` (seeded with Item Predictor hints)
- LLM generates a structured list of BOQ items with description, unit, and quantity.
- Each item is tagged `source: "llm_baseline"`.

#### Sub-stage 3c — LLM Gap-Fill
- **Prompt:** `gap_fill_boq_items.txt`
- LLM compares baseline list against Item Predictor predictions.
- Adds only items that are genuinely missing.
- New items tagged `source: "item_predictor"` or `source: "llm_gap_fill"`.

**Each BOQ item dict at this point:**
```json
{
  "description": "Excavation in ordinary soil, depth ≤ 1.5 m",
  "category": "excavation_and_earthwork",
  "section": "Excavation & Earthwork",
  "source": "llm_baseline",
  "floors": 2
}
```

**Category assignment** is done by regex rules mapping keywords → 18 categories.

---

### Stage 4 — RAG / BSR Matching

**Files:** `services/rag_process/`, `infrastructure/data_layer/vector_db/`

**What it does:**
For each BOQ item, finds the best matching BSR record using a hybrid retrieval + scoring approach:

1. **Query normalisation** — lowercase, remove noise words, strip quantity prefixes.
2. **Feature extraction** — detect `work_type`, `material`, `method`, `constraints` from the query text.
3. **Semantic retrieval** — embed query with `sentence-transformers`, query ChromaDB for top-k candidates.
4. **Full record fetch** — load candidate BSR records from PostgreSQL by ID.
5. **Deterministic scoring:**
   ```
   final_score = 0.65 × vector_score + 0.35 × keyword_score
   ```
   Keyword scoring rules:
   - `+3` exact material match
   - `+2` work_type match
   - `+2` method match
   - `+1` constraints match
   - `+1` partial token overlap (≥3 tokens)
   - Normalised to [0, 1] by dividing by 9.

6. **Three-tier confidence:**
   - `final_score < 0.30` → `no_match`
   - `0.30 ≤ score < MIN_CONFIDENCE_THRESHOLD (0.45)` → `soft_match`
   - `score ≥ 0.45` → `confirmed`

**Each BOQ item is enriched with:**
```json
{
  "bsr_item_no": "3.1.2",
  "bsr_description": "Excavation in ordinary soil ...",
  "unit": "cum",
  "rate": 350.0,
  "match_confidence": 0.83,
  "match_type": "confirmed"
}
```

**BSR Data Source:** `bsr_wp_2025.pdf` — parsed with `pdfplumber` and stored in PostgreSQL + ChromaDB on first startup.

---

### Stage 5 — Quantity Take-Off Engine

**File:** `services/quantity_gen_process/service.py`

**Branch A — Floorplan geometry available:**
- Apply deterministic geometry/rule-based formulas per BOQ item category (e.g., excavation = `area × 1.15`).
- For items where no geometry rule applies → Quantity Predictor (ML).
- Sources tagged: `"geometry"`, `"rule_based"`, or `"quantity_predictor"`.

**Branch B — No floorplan:**
- All items go through Quantity Predictor.
- Sources tagged: `"quantity_predictor"`.

**Geometry rules coverage** (`rule_based_calculator.py`):

| Category | Formula |
|---|---|
| Preliminary & General | 1 (lump sum) |
| Excavation & Earthwork | `area × 1.15` |
| Piling & Substructure | `area × floors × 0.6` |
| Concrete Works / Formwork / Reinforcement | `area × floors × 0.75` |
| Brick Masonry | `wall_length × floor_height × floors − openings × 2 m²` |
| Plastering & Rendering | same as brick masonry |
| Flooring & Tiling | `area × floors` |
| Roofing & Ceiling | `area × 1.1` |
| Doors, Windows & Glazing | `opening_count` |
| Sanitary & Plumbing | `bathrooms × floors` |
| Painting & Finishes | `wall_face_area + floor_area` |

**Quantity Predictor (ML):** `quantity_predictor.joblib` — sklearn regression model trained on log1p-transformed quantities; inverted with `expm1`. Has both a global model and per-item models.

---

### Stage 6 — Validation

**File:** `services/validation/quantity_validator.py`

**What it does:**
- Iterates all BOQ items.
- Flags any item where `quantity ≤ 0` with a warning string.
- Returns `{ warnings: [...], is_valid: bool }`.

---

### Stage 7 — Cost Calculation

**File:** `services/pricing_process/cost_calculator.py`

**What it does:**
```
cost_per_item = rate × quantity
base_total    = Σ cost_per_item
contingencies = base_total × 0.05   (5% fixed)
total         = base_total + contingencies
```
- Groups costs into subtotals by category.
- Returns enriched items list with `cost` field added.

---

### Stage 8 — Transparency & Confidence

**File:** `services/validation/confidence_scoring.py`

**What it does:**
- Starts with a **hardcoded baseline of 0.70**.
- `+0.10` if floorplan geometry was available.
- `+0.10` if project parameters are present.
- `−0.05 × warning_count` (capped at −0.20) for validation warnings.
- Clamped to [0.0, 1.0].

**Source summary** (`_build_source_summary` in pipeline):
- Counts items by `quantity_source` and `match_type`.

---

### Stage 9 — Reporting

**File:** `services/reporting_process/report_builder.py`

**What it does:**
- Assembles the final JSON response payload with `summary` and `details`.
- `summary` includes: `total`, `confidence`, project parameters, source breakdown.
- `details` contains the full pipeline payload.

**Output is JSON only.** Excel and PDF generators are **empty placeholders.**

---

## 6. API Endpoints

All routes are prefixed with `/api`.

| Method | Path | Description |
|---|---|---|
| `GET` | `/` | Health check |
| `POST` | `/api/match-boq` | Single BOQ item → BSR match |
| `POST` | `/api/ingest-bsr` | Ingest BSR PDF into DB + vector store |
| `POST` | `/api/rag/diagnose` | Diagnostic: show top BSR candidates for multiple BOQ descriptions |
| `POST` | `/api/estimate-project/stream/start` | Start non-interactive estimation (SSE) |
| `GET` | `/api/estimate-project/stream/{session_id}` | SSE stream for estimation progress |
| `POST` | `/api/estimate-project/clarification/start` | Start clarification session |
| `POST` | `/api/estimate-project/clarification/{session_id}/answer` | Submit clarification answer |
| `GET` | `/api/estimate-project/clarification/stream/{session_id}` | SSE stream for clarification |
| `POST` | `/api/floorplan-ocr` | Extract dimensions from a floorplan image |
| `GET` | `/api/documents/` | List available documents |

---

## 7. Frontend

**Stack:** Next.js, TypeScript, Tailwind CSS, UploadThing

**Single page app** (`src/app/page.tsx`):
- Chat interface with message history.
- User types a project description; optional floorplan upload via UploadThing.
- Starts a clarification session (`POST .../clarification/start`).
- Opens SSE stream (`EventSource`); renders question/answer turns in the chat.
- Formats final BOQ as a readable text block.
- "New Chat" button resets state.

**API Client** (`src/services/estimation.ts`):
- `startClarificationSession()` — POST to start session.
- `submitClarificationAnswer()` — POST answer per question.
- `openClarificationStream()` — opens `EventSource`.

**Environment variable:** `NEXT_PUBLIC_API_BASE_URL` — defaults to `http://localhost:8000`.

---

## 8. ML Models

### Item Predictor (`item_predictor.joblib`)

| Aspect | Detail |
|---|---|
| Algorithm | scikit-learn `MultiOutputClassifier` wrapping Random Forest |
| Input features (6) | `Total_Area`, `Floors`, `Budget_enc`, `Project_Type_enc`, `Roof_Type_enc`, `Ceiling_Type_enc` |
| Output | Multi-label work-category predictions → mapped to item description strings |
| Artifact keys | `model`, `mlb`, `label_encoders`, `feature_cols`, `budget_order`, `cat_to_items`, `best_model_name`, `metrics` |
| Load strategy | Lazy singleton on first call |

### Quantity Predictor (`quantity_predictor.joblib`)

| Aspect | Detail |
|---|---|
| Algorithm | sklearn regression (global + per-item models) |
| Input features | `area_imputed`, `log_area`, `area_per_floor`, `log_area_floor`, `No. of Floors`, `Year`, `is_renovation`, plus categorical columns |
| Target | `log1p(quantity)` — predictions inverted with `expm1` |
| Artifact keys | `model`, `label_encoders`, `item_models`, `feature_cols`, `num_cols`, `cat_cols` |

### YOLO Object Detector (`new_best.pt`)

| Aspect | Detail |
|---|---|
| Framework | Ultralytics YOLOv8 |
| Classes | `0=door`, `1=window`, `2=zone` |
| Use | Count doors/windows, detect room zone areas from floorplan images |
| Pixel-to-m² | `pixels_to_m2()` helper in `yolo_detector.py` |

---

## 9. RAG System Detail

### Ingest Flow

```
bsr_wp_2025.pdf
     │
     ▼ pdfplumber
Parsed rows [{item_no, description, unit, rate, category, ...}]
     │
     ▼ SQLAlchemy
PostgreSQL bsr_items table
     │
     ▼ sentence-transformers  (item_no + description + category)
Embeddings
     │
     ▼ ChromaDB
Vector store (persistent)
```

### Query Flow

```
BOQ item description
     │
     ▼ normalize_query() + extract_query_features()
QueryFeatures {work_type, material, method, constraints, tokens}
     │
     ▼ EmbeddingProvider.embed_one()
Query embedding
     │
     ▼ ChromaBSRVectorStore.query() — top-k candidates
candidate IDs + vector_scores
     │
     ▼ get_bsr_items_by_ids() — PostgreSQL
Full BSRItem records
     │
     ▼ score_candidate() per candidate
{vector_score, keyword_score, final_score, matched_fields}
     │
     ▼ select best, apply confidence tier
Result
```

---

## 10. Known Issues & Areas That Need Improvement

The following list identifies components that are incomplete, heuristic-based, or architecturally weak. Items are grouped by severity.

---

### 🔴 Critical — Missing Implementation

| # | File(s) | Issue |
|---|---|---|
| 1 | `services/reporting_process/excel_generator.py` | **Empty placeholder.** No Excel export exists. The pipeline builds a JSON report only. |
| 2 | `services/reporting_process/pdf_generator.py` | **Empty placeholder.** No PDF export exists. |
| 3 | `services/pricing_process/service.py` | **Empty placeholder.** The pricing service facade has no logic; `cost_calculator.py` is called directly from the pipeline bypassing the service layer. |
| 4 | `app/worker/tasks/` | **Celery tasks are stubs.** The docker-compose has no worker service. Background job processing (e.g., long-running estimations) is not implemented — everything runs synchronously in the API process. |

---

### 🟠 High — Incomplete or Fragile Logic

| # | File(s) | Issue |
|---|---|---|
| 5 | `services/floorplan_process/pipeline.py` | **Perimeter is approximated** as `4 × √(area)` (assumes a square footprint). Real buildings are not square. This directly affects wall-area quantities for masonry, plastering, and painting. |
| 6 | `services/validation/confidence_scoring.py` | **Confidence score starts at a hardcoded 0.70 baseline** regardless of how many BOQ items had `no_match` or `soft_match` BSR results. The actual match rate is not factored in. |
| 7 | `services/validation/quantity_validator.py` | **Validation only checks for non-positive quantities.** No range validation (e.g., is 10,000 m³ of excavation realistic for a 2-storey house?). `boq_validator.py` and `confidence_scoring.py` exist but `boq_validator.py` is not called in the pipeline. |
| 8 | `services/quantity_gen_process/quantity_calculator.py` | If `quantity_predictor.joblib` is missing, all ML-predicted quantities silently default to `0`. This produces zero-cost items in the estimate with no user-visible warning beyond a log entry. |
| 9 | `app/api/state/session.py` | **Sessions are stored in-memory.** A server restart loses all active sessions. Sessions cannot be shared across multiple API worker processes. |
| 10 | `infrastructure/integrations/openrouter_client.py` | **Mock fallback is unconditional in `development` ENV.** If the OpenRouter API key is missing, the mock returns minimal static JSON, which silently produces a useless estimate. |

---

### 🟡 Medium — Design Gaps

| # | File(s) | Issue |
|---|---|---|
| 11 | `app/api/server.py`, `app/api/routes/router.py` | **No authentication or authorisation.** All endpoints are publicly accessible. |
| 12 | `app/api/routes/router.py` | **No rate limiting.** Each estimation triggers multiple LLM calls and ML inferences; the API is open to abuse. |
| 13 | `services/item_gen_process/boq_builder.py` | **Category assignment uses regex on the LLM-generated description text.** If the LLM describes an item differently from the expected vocabulary, it falls through to `"misc"`, breaking quantity rule-based calculation for that item. |
| 14 | `services/rag_process/retriever.py` | **MATERIAL_HINTS, WORK_TYPES, and METHODS are hardcoded lists.** New BSR categories added to the PDF will not be matched unless the lists are manually updated. |
| 15 | `services/pricing_process/cost_calculator.py` | **Contingency rate is hardcoded at 5%.** It should be configurable per project or region. |
| 16 | `services/reporting_process/report_builder.py` | **Report only includes project-level summary fields** (`floors`, `bedrooms`, etc.). It does not include per-item BSR match details or confidence flags in the summary — the frontend has to dig into `details`. |
| 17 | `frontend/src/app/page.tsx` | **No error recovery in the SSE stream.** If the stream disconnects mid-estimation, the UI shows nothing. There is no retry logic or timeout indicator. |
| 18 | `frontend/src/app/page.tsx` | **BOQ formatting is basic text.** The result is rendered as a plaintext block with no table, sorting, filtering, or cost breakdown by category. |

---

### 🔵 Low — Technical Debt & Minor Issues

| # | File(s) | Issue |
|---|---|---|
| 19 | `backend/app/api/schemas/` | **Schemas directory is empty.** Pydantic models are defined inline in controllers. Should be moved to schemas for reusability and OpenAPI documentation. |
| 20 | `backend/tests/unit/`, `backend/tests/integration/` | **Test directories are empty.** No automated tests exist for any service, model, or endpoint. |
| 21 | `services/floorplan_process/pipeline.py` | `_preprocess` and `_ocr` raw sub-results are included in the geometry dict as `_preprocess` and `_ocr` keys, leaking internal debug data into the pipeline's data flow. |
| 22 | `application/pipelines/estimation_pipeline.py` | **`_dev_log` function logs every intermediate payload to disk.** In production this will generate large log files and expose sensitive project data. |
| 23 | `docker/docker-compose.yml` | **The API and worker services are not in docker-compose.** Only the databases are containerised. Local dev requires manually starting uvicorn. |
| 24 | `core/config/settings.py` | **`POSTGRES_PASSWORD` is a required string env var with no validation beyond "not empty".** Weak or default passwords will pass silently. |

---

### Summary Table

| Severity | Count | Areas |
|---|---|---|
| 🔴 Critical (not implemented) | 4 | Excel export, PDF export, pricing service, background workers |
| 🟠 High (fragile/wrong) | 6 | Perimeter heuristic, confidence scoring, validation depth, zero-quantity silent failure, in-memory sessions, mock fallback |
| 🟡 Medium (design gaps) | 8 | Auth, rate limiting, category regex, hardcoded lists, fixed contingency, report detail, SSE error handling, frontend formatting |
| 🔵 Low (tech debt) | 6 | Inline schemas, no tests, debug data leaks, dev logging in prod, partial docker-compose, password validation |

---

*Generated from codebase analysis — April 2026*

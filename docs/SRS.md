# Software Requirements Specification (SRS)

**Project:** AI-Assisted Construction Cost Estimation System
**Domain:** Sri Lankan Residential / Commercial / Industrial Construction
**Document version:** 1.0
**Date:** 2026-05-09

---

## Table of Contents

1. [Introduction](#1-introduction)
2. [Overall Description](#2-overall-description)
3. [System Architecture (As-Implemented)](#3-system-architecture-as-implemented)
4. [Currently Implemented Functional Requirements](#4-currently-implemented-functional-requirements)
5. [Currently Implemented Non-Functional Requirements](#5-currently-implemented-non-functional-requirements)
6. [Diagnosis of the Observed Output (25 items, 20.6 % confidence, LKR 56.8 M)](#6-diagnosis-of-the-observed-output-25-items-206--confidence-lkr-568-m)
7. [Required Improvements to Existing Functionalities](#7-required-improvements-to-existing-functionalities)
8. [New Functional Requirements to Be Implemented](#8-new-functional-requirements-to-be-implemented)
9. [Confidence-Score Improvement Plan](#9-confidence-score-improvement-plan)
10. [Acceptance Criteria & Target KPIs](#10-acceptance-criteria--target-kpis)
11. [Out of Scope](#11-out-of-scope)
12. [Glossary](#12-glossary)

---

## 1. Introduction

### 1.1 Purpose

This SRS describes the **current state** and the **required future state** of the AI-assisted BOQ generation and cost estimation system. It is written for the developer (final-year project author), supervisors, and reviewers who need to understand:

- which functionalities are already implemented,
- why the present output (25 BOQ items, 20.6 % confidence — see attached screenshot) is **not sufficient** to estimate a real residence,
- which improvements and new functionalities are required to reach a production-grade BOQ and a confidence score above 0.75.

### 1.2 Intended Audience

- Project author / developer
- Academic supervisors and examiners
- Quantity Surveyor (QS) reviewers acting as domain testers
- Future maintainers

### 1.3 Scope

The system accepts:

- a structured project description entered through a multi-step wizard, **and / or**
- one or more uploaded floorplan images,

and produces:

- a Bill of Quantities (BOQ) item list,
- BSR-matched item codes, units, and rates,
- per-item quantities,
- a costed estimate (base cost + preliminaries + contingencies),
- a confidence score and source-transparency report,
- a downloadable Excel (and, in future, PDF) report.

### 1.4 Definitions

See [Glossary](#12-glossary).

---

## 2. Overall Description

### 2.1 Product Perspective

The system is a single-tenant web application composed of:

- a **Next.js / TypeScript** frontend (wizard form, SSE progress, results page, Excel download),
- a **FastAPI / Python 3.11** backend running a 12-stage estimation pipeline,
- a **PostgreSQL** relational store (BSR rate table; current wizard / estimation sessions remain in process memory),
- a **ChromaDB** vector store (BSR embeddings),
- a set of **ML artefacts** (item-predictor Random Forest, quantity-predictor regression, YOLOv8 floorplan model),
- an **OpenRouter LLM gateway** for generative reasoning steps.

### 2.2 User Classes

| User class | Description | Primary actions |
|---|---|---|
| Estimator (QS / engineer / homeowner) | Submits a project | Fills wizard, uploads floorplans, downloads Excel |
| Reviewer | Inspects estimate quality | Reads confidence report, audits item list |
| Developer / Admin | Maintains the system | Ingests BSR PDF, monitors logs, retrains models |

### 2.3 Operating Environment

- Local Docker Compose for PostgreSQL + ChromaDB.
- Local Uvicorn process for the FastAPI app.
- `npm run dev` for the Next.js frontend.
- Tested on Windows; Python 3.11+; Node 18+.

### 2.4 Assumptions and Dependencies

- BSR 2025 (Western Province) rates are authoritative.
- OpenRouter API key is available (otherwise development mock returns degraded JSON).
- Tesseract OCR and YOLO weights (`new_best.pt`) are installed locally.

---

## 3. System Architecture (As-Implemented)

### 3.1 Pipeline Stages

The estimation flow is implemented in [backend/application/pipelines/estimation_pipeline.py](backend/application/pipelines/estimation_pipeline.py) as a 12-stage orchestrator:

1. Floorplan download & cache (optional).
2. Floorplan CV pipeline → geometry dict (YOLO + Tesseract).
3. Item Predictor (Random Forest) → candidate work-category items that seed the BOQ generator.
4. LLM Baseline BOQ generation → initial structured item list (LLM QS pass, seeded with Stage 3 predictor hints).
5. LLM Gap-Fill → final BOQ list (compares the Stage 4 baseline against Stage 3 predictor candidates and adds missing items).
6. RAG matching against BSR vector + relational store.
7. Quantity Take-Off (geometry rules / parametric / ML, fused with weights).
7.5. BOQ structural validation — wired here as a retroactive fix; see IMP-VAL-01 for the planned move to before Stage 6.
8. Quantity range / anomaly validation.
9. Cost calculation (rate × quantity + preliminaries + contingencies).
10. Confidence & transparency scoring.
11. Reporting (JSON; Excel partially wired).

### 3.2 Component Map

| Component | Code path |
|---|---|
| API server | [backend/app/api/server.py](backend/app/api/server.py) |
| Routes | [backend/app/api/routes/router.py](backend/app/api/routes/router.py) |
| Form controller | [backend/app/api/controllers/form_controller.py](backend/app/api/controllers/form_controller.py) |
| Session store | [backend/app/api/state/session.py](backend/app/api/state/session.py) |
| Item generation | [backend/services/item_gen_process/boq_builder.py](backend/services/item_gen_process/boq_builder.py) |
| Item predictor (ML) | [backend/services/item_gen_process/item_predictor.py](backend/services/item_gen_process/item_predictor.py) |
| LLM client | [backend/services/item_gen_process/llm_client.py](backend/services/item_gen_process/llm_client.py) |
| RAG service | [backend/services/rag_process/service.py](backend/services/rag_process/service.py) |
| RAG matcher | [backend/services/rag_process/matcher.py](backend/services/rag_process/matcher.py) |
| Quantity engine | [backend/services/quantity_gen_process/service.py](backend/services/quantity_gen_process/service.py) |
| Rule-based qty | [backend/services/quantity_gen_process/rule_based_calculator.py](backend/services/quantity_gen_process/rule_based_calculator.py) |
| Cost calc | [backend/services/pricing_process/cost_calculator.py](backend/services/pricing_process/cost_calculator.py) |
| Validation | [backend/services/validation/boq_validator.py](backend/services/validation/boq_validator.py) |
| Confidence | [backend/services/validation/confidence_scoring.py](backend/services/validation/confidence_scoring.py) |
| Floorplan CV | [backend/services/floorplan_process/orchestrator.py](backend/services/floorplan_process/orchestrator.py) |
| Reporting | [backend/services/reporting_process/report_builder.py](backend/services/reporting_process/report_builder.py) |

---

## 4. Currently Implemented Functional Requirements

### 4.1 Project Intake — Wizard (Frontend)

The intake UI is a **5-step wizard** implemented in [frontend/src/app/page.tsx](frontend/src/app/page.tsx) using the step types defined in [frontend/src/types/wizard.ts](frontend/src/types/wizard.ts).

| Step | Component | Collects |
|---|---|---|
| 1 — Project Basics | [ProjectBasicsStep.tsx](frontend/src/components/wizard/steps/ProjectBasicsStep.tsx) | Building type (residential / commercial / industrial), floor count, optional free-text description, zero or more floorplan images (drag-and-drop via UploadThing) |
| 2 — Floor Areas | [FloorAreasStep.tsx](frontend/src/components/wizard/steps/FloorAreasStep.tsx) | Per-floor area rows (label, area value, unit sqft/m²); auto-generated from floor count |
| 3 — Building Program | [BuildingProgramStep.tsx](frontend/src/components/wizard/steps/BuildingProgramStep.tsx) | Residential: bedrooms, bathrooms; Commercial: primary use type, washroom count; Industrial: facility type, heavy machinery load, hazardous materials, specialised ventilation |
| 4 — Construction Details | [ConstructionDetailsStep.tsx](frontend/src/components/wizard/steps/ConstructionDetailsStep.tsx) | Finish level, structural system, roof type, ceiling type, location, soil condition, drainage type, external works scope |
| 5 — Review & Submit | [ReviewSubmitStep.tsx](frontend/src/components/wizard/steps/ReviewSubmitStep.tsx) | Read-only summary of all collected data with per-section Edit shortcuts; Submit button triggers estimation |

- **FR-INTAKE-01** Wizard step progress is shown in [WizardProgress.tsx](frontend/src/components/wizard/WizardProgress.tsx) with an animated progress bar and numbered step circles (complete / current / pending states).
- **FR-INTAKE-02** Client-side step validation enforces mandatory fields before advancing (building type, floor count ≥ 1, per-floor area > 0, bedrooms/bathrooms, finish level, structural system, roof type, ceiling type).
- **FR-INTAKE-03** Wizard payload is validated server-side ([form_controller.py](backend/app/api/controllers/form_controller.py)) and normalised into `project_info`.
- **FR-INTAKE-04** Sri Lankan defaults are applied for any optional fields not provided ([clarification_process/service.py](backend/services/clarification_process/service.py)).
- **FR-INTAKE-05** Floorplan files are uploaded via `useUploadThing("floorplanUploader")` with per-file status indicators (pending / uploading / done / error); CDN URLs are collected into `floorplan_urls` and submitted with the form payload.

### 4.2 Floorplan Processing (Optional)

- **FR-CV-01** YOLOv8 (`new_best.pt`) detects doors, windows, and zone polygons.
- **FR-CV-02** Tesseract OCR extracts dimension text from the image.
- **FR-CV-03** Multiple floorplans are merged into one geometry dict ([geometry_merger.py](backend/services/floorplan_process/geometry_merger.py)).
- **FR-CV-04** Geometry confidence is scored ([confidence_scorer.py](backend/services/floorplan_process/confidence_scorer.py)).

### 4.3 BOQ Item Generation (3-Stage)

- **FR-BOQ-01** Item Predictor (Stage 3) runs first and produces candidate work-category items with per-item source confidence; those descriptions are passed forward as hints to the baseline LLM step.
- **FR-BOQ-02** LLM baseline generation (Stage 4), seeded with predictor hints, produces an initial structured item list with `description`, `category`, `section`.
- **FR-BOQ-03** LLM Gap-Fill pass (Stage 5) compares the Stage 4 baseline against Stage 3 predictor candidates and returns the reconciled final BOQ; output items tagged `source = llm_reconciled / llm_baseline / item_predictor`.
- **FR-BOQ-04** Fuzzy de-duplication (similarity ≥ 0.90) collapses near-duplicates.
- **FR-BOQ-05** Each item is enriched with `unit`, `material_type`, and ML work-category mapping.
- **FR-BOQ-06** Empty BOQ raises `EstimationError`.

### 4.4 RAG / BSR Matching

- **FR-RAG-01** BSR PDF is ingested into PostgreSQL + ChromaDB on first startup.
- **FR-RAG-02** For each item, vector retrieval (top-k) + keyword scoring produces a final score.
- **FR-RAG-03** Three-tier classification: `confirmed` ≥ 0.45, `soft_match` 0.30-0.45, `no_match` < 0.30.
- **FR-RAG-04** Contractual items (preliminaries, securities) are bypassed and tagged `contractual` with rate 0.

### 4.5 Quantity Take-Off

- **FR-QTY-01** Geometry-available branch: per-category formulas (`area × floors × X`, `wall_length × height − openings`, etc.) plus ML.
- **FR-QTY-02** Geometry-absent branch: parametric rules + ML predictor.
- **FR-QTY-03** Candidates are fused with unit-aware confidence weights ([confidence_scoring.py](backend/services/quantity_gen_process/confidence_scoring.py)).
- **FR-QTY-04** Per-item warnings (non-positive qty) are emitted by [quantity_validator.py](backend/services/quantity_gen_process/quantity_validator.py).

### 4.6 Cost Calculation

- **FR-COST-01** `cost = rate × quantity` per item.
- **FR-COST-02** Base total + preliminaries (8 % default) + contingencies (5 % default) → grand total.
- **FR-COST-03** Per-category subtotals.

### 4.7 Validation & Confidence

- **FR-VAL-01** Structural BOQ validation: non-empty, has description, has unit, has category ([boq_validator.py](backend/services/validation/boq_validator.py)).
- **FR-VAL-02** Quantity validation flags `quantity <= 0`.
- **FR-VAL-03** Confidence score uses base 0.50 + bonuses/penalties (floorplan, defaults, validation, match rate, geometry confidence, feature completeness, disagreement).

### 4.8 Reporting

- **FR-REP-01** Final JSON payload returned by the backend pipeline includes top-level `boq_items`, `costs`, `validation`, `confidence`, and `sources`, plus a nested `report` object whose `summary` and `details` fields are built by [report_builder.py](backend/services/reporting_process/report_builder.py).
- **FR-REP-02** Excel report is generated **client-side** in the browser using **SheetJS (`xlsx`)** inside `generateExcelReport()` in [page.tsx](frontend/src/app/page.tsx). The workbook contains three sheets:
  - *Summary* — project details and cost summary.
  - *Bill of Quantities* — full item list with BSR code, description, unit, quantity, rate, cost, and match %.
  - *Cost Breakdown* — per-category subtotals sorted by cost.
  The generated `.xlsx` blob is then uploaded to UploadThing and a download URL (`excelUrl`) is set for the `Download Excel Report` button. **Privacy note:** this uploads a client's construction cost data (rates, quantities, totals) to a third-party CDN; IMP-FE-05 addresses this by making a direct `Blob` URL download the default path and treating the UploadThing upload as an optional fallback. The backend `excel_generator.py` is **still a placeholder** and is not used.
- **FR-REP-03** Results page shows three summary cards (Grand Total, Confidence Score, BOQ Items count) and a **top-5 BOQ preview table** (description, unit, qty, rate, cost + grand total footer row).

### 4.9 Real-Time Progress

- **FR-SSE-01** Frontend opens an `EventSource` via `openFormEstimateStream(session_id)` ([estimation.ts](frontend/src/services/estimation.ts)) to `GET /api/estimate-project/form/stream/{session_id}`.
- **FR-SSE-02** Four named SSE event types are handled:
  - `progress` → updates the `pipelineStep` status label shown during estimation.
  - `info` → updates the same status label with informational messages.
  - `completed` → closes the stream, populates the result state, generates Excel, and navigates to the results view.
  - `error` → closes the stream and surfaces a human-readable error message.
- **FR-SSE-03** No separate development-only diagnostic SSE endpoint is currently routed; live progress is exposed only through the primary form estimation stream in [form_controller.py](backend/app/api/controllers/form_controller.py).

### 4.10 Diagnostic / Admin

- **FR-DIAG-01** `POST /api/match-boq` for single-item RAG match.
- **FR-DIAG-02** No routed `POST /api/rag/diagnose` or `GET /api/documents/` endpoints are currently exposed in [router.py](backend/app/api/routes/router.py); richer diagnostic / admin browse endpoints remain future work.

### 4.11 Frontend API Client

All backend calls originate from [frontend/src/services/estimation.ts](frontend/src/services/estimation.ts):

| Function | HTTP call | Purpose |
|---|---|---|
| `validateWizardForm(payload)` | `POST /api/estimate-project/form/validate` | Server-side validation before final submit |
| `submitWizardForm(payload)` | `POST /api/estimate-project/form/submit` | Creates session, fires pipeline async; returns `session_id` |
| `openFormEstimateStream(sessionId)` | `GET /api/estimate-project/form/stream/{id}` | Opens SSE stream for live progress and final result |

### 4.12 Frontend Type System

All wizard data shapes are centralised in [frontend/src/types/wizard.ts](frontend/src/types/wizard.ts):

- `BuildingType`, `FinishLevel`, `RoofType`, `CeilingType`, `StructuralSystem`, `SoilCondition`, `DrainageType`, `ExternalWorksScope`, `ConstructionScope`, `ConcreteGrade`, `WallType`, `SanitaryFittingGrade`, `ElectricalScopeLevel`, `WaterproofingRequirement` — canonical enum strings matching backend slugs.
- `ProjectBasics`, `FloorAreas`, `BuildingProgram`, `ConstructionDetails` — per-step data interfaces.
- `WizardFormData` — top-level aggregation of all steps.
- `ExcelPreviewRow` — shape of the top-5 preview table rows.
- `WIZARD_STEPS` — ordered step metadata array driving `WizardProgress`.

### 4.13 Frontend Infrastructure

- **UploadThing** ([frontend/src/app/api/uploadthing/](frontend/src/app/api/uploadthing/), [lib/uploadthing.ts](frontend/src/lib/uploadthing.ts)) — provides two file routers: `floorplanUploader` (accepts images, used in Step 1) and `excelUploader` (accepts `.xlsx`, used after estimation completes).
- **Mobile responsiveness** — `use-mobile.ts` hook and Tailwind responsive classes.
- **shadcn/ui component set** — `button`, `card`, `input`, `separator`, `sheet`, `sidebar`, `skeleton`, `tooltip` used in wizard steps.
- **Next.js App Router** with a single route (`/`) housing the wizard + results page.

---

## 5. Currently Implemented Non-Functional Requirements

| ID | Requirement | Status |
|---|---|---|
| NFR-PERF-01 | Single estimation completes in ≤ 60 s for a typical 2-storey house | ✓ usually met |
| NFR-PERF-02 | RAG batch matching is parallel-safe | ✓ |
| NFR-OBS-01 | Three-file logging (app, error, pipeline) | ✓ |
| NFR-OBS-02 | Per-stage SSE progress stream | ✓ |
| NFR-CFG-01 | Settings are env-driven via [settings.py](backend/core/config/settings.py) | ✓ |
| NFR-RES-01 | Pipeline must not crash if floorplan processing fails | ✓ (graceful degradation) |
| NFR-SEC-01 | Authentication / authorisation | ✗ (not implemented) |
| NFR-SEC-02 | Rate limiting | ✗ (not implemented) |

---

## 6. Diagnosis of the Observed Output (25 items, 20.6 % confidence, LKR 56.8 M)

The attached results screenshot shows three symptoms that, taken together, indicate the system is currently operating at a **proof-of-concept** rather than production level.

### 6.1 Symptom A — Only 25 BOQ items

A real Sri Lankan two-storey residence carries **roughly 120-220 BSR line items** in a professional BOQ (preliminaries, substructure, superstructure, finishes, MEP, externals, contingencies). Twenty-five items is enough to compute a headline cost but cannot represent:

- per-floor concrete grades and slab thicknesses,
- separate items for columns / beams / slabs / lintels / staircases,
- door and window schedules with sizes and ironmongery,
- electrical schedule (points, circuits, DBs, wiring),
- plumbing schedule (fixtures, hot/cold pipework, waste, traps, sumps),
- interior finishes per room type,
- external works (paving, boundary wall, gate, drainage, landscaping),
- testing & commissioning items.

**Root causes (verified in code):**

1. The LLM generates only what the prompt requests. The current prompt in [generate_baseline_boq.txt](backend/infrastructure/integrations/prompt_templates/generate_baseline_boq.txt) asks for a "comprehensive" list but supplies **no minimum count, no mandatory sections, and no quantity guidance per floor**.
2. The reconciliation/gap-fill step ([gap_fill_boq_items.txt](backend/infrastructure/integrations/prompt_templates/gap_fill_boq_items.txt)) merges only what the LLM returns; it does not enforce a checklist of mandatory residential sections.
3. Fuzzy de-duplication (threshold 0.90) is permissive and may collapse items that differ only in floor or material grade ("Brick masonry GF" vs "Brick masonry FF").
4. The `MultiOutputClassifier` Item Predictor is trained on **work-categories**, not line items, so its hints are coarse-grained.
5. There is no explicit **per-floor expansion** stage that turns one logical item ("brick masonry to walls") into one item per floor or per location.

### 6.2 Symptom B — Confidence 20.6 %

Confidence scoring is implemented in [confidence_scoring.py](backend/services/validation/confidence_scoring.py). The current penalty model contains terms that legitimately drive the score down:

- `unmatched_items / total` → penalty up to −0.30.
- `needs_rate_review` items → penalty up to −0.15.
- `low_geometry_confidence` → penalty up to −0.15.
- `defaults_applied` → penalty up to −0.20.
- Validation warnings → penalty up to −0.20.

For the screenshot run, we can infer that:

- The first two preview rows ("Allow for provision of advanced/performance payment security") have **rate = 0** — they are correctly flagged with `match_type = "contractual"` by `matcher.py`. However, `confidence_scoring.py` excludes items using `it.get("is_contractual")`, a field that `matcher.py` **never sets** (it sets `match_type`, not `is_contractual`). As a result the exclusion is silently inert and contractual items are still counted as unmatched. The fix in IMP-CONF-01 must change the check in `confidence_scoring.py` to `it.get("match_type") == "contractual"` to activate the exclusion correctly.
- Many BSR matches likely fall into `soft_match` / `no_match` because the LLM-generated descriptions do not use canonical BSR phrasing.
- The confidence formula is **additive of penalties** without a quality-of-coverage term (i.e., it does not credit the system for hitting all expected categories).

### 6.3 Symptom C — LKR 56.9 M total but only 5 visible high-cost items

The five preview items show:

- 2 × LKR 0 contractual lines,
- 1 × foundation line at LKR 11.87 M (m, qty 3 109.1 — unit looks wrong: foundation should be m³, not m),
- 1 × brick work 286.66 m³ × LKR 38 447 = LKR 11.02 M (plausible),
- 1 × ground-floor concrete 39.25 m³ × LKR 31 649 = LKR 1.24 M.

The foundation row demonstrates a **unit / quantity mismatch**: 3 109 metres of foundation for a residence is implausible. The `4 × √(area)` perimeter heuristic in `rule_based_calculator.py` is **not** the cause — for a typical 200 m² floor it yields `4 × √200 ≈ 56.6 m`, a realistic perimeter. The 3 109 m figure is instead caused by the **quantity being computed as a volume (m³) while the BSR-matched record carries the unit `m` (length)**: the numeric value of a volumetric take-off is passed through without dimensionality validation, producing a physically impossible length. The primary fix is therefore **IMP-QTY-02** (validate computed quantity against the BSR unit before fusion), not IMP-CV-01 alone.

---

## 7. Required Improvements to Existing Functionalities

The following requirements are **enhancements to already-implemented modules**.

### 7.1 BOQ Item Generation

- **IMP-BOQ-01** Replace the free-form LLM prompt with a **mandatory residential / commercial / industrial section template**: the prompt and a deterministic post-processor must guarantee items in every required section (Preliminaries, Substructure, Superstructure, Masonry, Finishes, Roofing, Doors & Windows, Electrical, Plumbing, External Works, Testing).
- **IMP-BOQ-02** Add a **minimum-coverage check** (`>= N items per category`, configurable per building type) after reconciliation; if a category is below the floor, trigger a **targeted re-prompt** for that category only.
- **IMP-BOQ-03** Generate **per-floor / per-location expansions** for items whose quantity scales with floors (concrete, masonry, plaster, painting, electrical points, plumbing fixtures). One logical item must become N items where N = floors × locations.
- **IMP-BOQ-04** Tighten fuzzy de-duplication to ignore matches when `floor`, `grade`, or `location` fields differ.
- **IMP-BOQ-05** Replace category regex with a small **embedding-based classifier** trained on BSR section headers — eliminates the `misc` fallback documented in [SYSTEM_README.md](SYSTEM_README.md) issue 13.

### 7.2 RAG / BSR Matching

- **IMP-RAG-01** Add **unit-aware re-ranking**: candidates whose unit disagrees with the BOQ item's expected unit lose points (prevents the m vs m³ foundation issue).
- **IMP-RAG-02** Convert hardcoded `MATERIAL_HINTS / WORK_TYPES / METHODS` ([retriever.py](backend/services/rag_process/retriever.py)) into **data-driven lists** built from BSR section headers at ingest time.
- **IMP-RAG-03** Promote `soft_match` to `confirmed` only after a **second-pass LLM verification** that the candidate description and the BOQ description describe the same work (already-supported pattern via the OpenRouter client).
- **IMP-RAG-04** Cache embeddings of BOQ descriptions to make retraining cheap.

### 7.3 Quantity Take-Off

- **IMP-QTY-01** Replace the perimeter approximation `4 × √(area)` with **one of**: (a) actual perimeter from YOLO zone polygons, (b) sum of OCR-detected wall lengths, (c) parametric perimeter from per-floor area + aspect ratio supplied by the wizard.
- **IMP-QTY-02** Validate computed quantity **against the BSR unit** before fusion; if unit does not match expected dimensionality (length / area / volume / count), drop the candidate.
- **IMP-QTY-03** Add **range checks per category** (e.g. excavation m³ must be within `area × 0.5 ≤ q ≤ area × 3.0` for a low-rise residence). Out-of-range items downgrade their candidate weight, not silently pass.
- **IMP-QTY-04** When `quantity_predictor.joblib` is missing, **fail loudly** and emit an explicit warning per item instead of defaulting to 0.

### 7.4 Validation

- **IMP-VAL-01** Move the [boq_validator.py](backend/services/validation/boq_validator.py) call to run **before** RAG (Stage 6). It is already wired in the pipeline at Stage 7.5 (after quantity take-off) as a retroactive fix, but that placement is too late — structurally malformed items enter RAG and quantity calculations before being caught. Relocate the call to immediately after Stage 5 (Gap-Fill) so that items lacking `description`, `unit`, or `category` are rejected before any downstream processing.
- **IMP-VAL-02** Add **completeness validator**: for the chosen building type, list of mandatory categories must all be present.
- **IMP-VAL-03** Add **unit-vs-category sanity validator** (e.g. `excavation_and_earthwork` must have unit `m³`, `painting_and_finishes` must have unit `m²`).
- **IMP-VAL-04** Add **price-per-square-metre sanity check** at totals level (Sri Lankan low-rise residential typical range LKR 18 000-35 000 per m² for standard finish in 2025); flag if out of range.

### 7.5 Confidence Scoring

- **IMP-CONF-01** Exclude `contractual` items from the unmatched-fraction calculation (they are intentionally rate-zero). **Implementation note:** `confidence_scoring.py` already contains the exclusion condition but checks `it.get("is_contractual")` — a field that `matcher.py` never writes (it writes `match_type = "contractual"` instead). Change the condition to `it.get("match_type") == "contractual"` to make the fix effective.
- **IMP-CONF-02** Add a **coverage bonus** of up to +0.15 when all mandatory categories for the building type are present.
- **IMP-CONF-03** Add a **per-section confidence breakdown** in the report so the reviewer sees which sections drag the overall score down.
- **IMP-CONF-04** Cap `defaults_applied` penalty: only count defaults for **cost-sensitive** fields (finish_level, roof_type, structural_system); ignore secondary defaults.

### 7.6 Cost Calculation

- **IMP-COST-01** Make preliminaries (8 %) and contingencies (5 %) **configurable per project** via the wizard.
- **IMP-COST-02** Add **regional rate adjustment** factor for projects outside Western Province (placeholder warning already exists in the prompt).
- **IMP-COST-03** Surface per-category subtotals in the results table on the frontend, not only the grand total.

### 7.7 Floorplan CV

- **IMP-CV-01** Replace the square-footprint perimeter heuristic (see IMP-QTY-01).
- **IMP-CV-02** Add a fallback **scale extraction** (OCR scale bar, dimension strings) to convert pixel area to m² reliably.
- **IMP-CV-03** Persist the extracted geometry alongside the original image so the QS can audit the CV result.

### 7.8 Reporting

- **IMP-REP-01** The client-side Excel report ([page.tsx](frontend/src/app/page.tsx) `generateExcelReport()`) already produces 3 sheets. Extend it with: a fourth **Audit sheet** (match_type, match_confidence, quantity_source, quantity_confidence_score per item) and per-item warning flags. Also apply column auto-width and a header row freeze for usability.
- **IMP-REP-02** Implement the backend placeholder Excel generator ([excel_generator.py](backend/services/reporting_process/excel_generator.py)) as a server-side alternative — required for large BOQs where client-side generation may be too slow, and for future server-initiated report dispatch.
- **IMP-REP-03** Implement the placeholder PDF generator ([pdf_generator.py](backend/services/reporting_process/pdf_generator.py)) for printable, signed reports.
- **IMP-REP-04** Include `match_type`, `match_confidence`, and `quantity_source` in both the frontend Audit sheet and the backend JSON summary so reviewers see which items are weak without opening the full `details` payload.

### 7.9 Frontend

- **IMP-FE-01** Results page currently shows only the **top-5 BOQ preview** (`excelPreview.slice(0, 5)`). Replace with a full, paginated or virtualised BOQ table with column-level sorting, text filtering, and grouping by section/category.
- **IMP-FE-02** Highlight rows where `match_type = no_match` or `needs_rate_review = true` with a distinct colour or icon; allow inline editing of quantity and rate for those rows.
- **IMP-FE-03** The current frontend already relies on the browser's native `EventSource` automatic reconnect behavior and intentionally ignores empty native network / reconnect error events. Improve reliability by adding a visible stalled-pipeline indicator if no event arrives within 30 s, and add explicit custom reconnect logic only if the transport is changed or duplicate-stream handling is implemented.
- **IMP-FE-04** Add an editable "Override quantities & rates" mode for QS users before triggering the Excel download; edited values should be reflected in both the client-side Excel and in a recompute call to the backend (see NEW-EDIT-02).
- **IMP-FE-05** The `excelUrl` is set via a secondary UploadThing upload after estimation completes. If this upload fails, the Download button never appears but there is no visible error. Add a fallback: if the UploadThing upload fails, offer a direct `Blob` URL download instead.
- **IMP-FE-06** The Review & Submit step (Step 5) does not preview the uploaded floorplan image thumbnails. Add a thumbnail strip so the user can confirm the correct images were attached.
- **IMP-FE-07** Add a **per-category cost breakdown chart** (bar or pie) on the results page using the `costs.subtotals` data already returned by the API.
- **IMP-FE-08** The current single-page app has no navigation, route guards, or protected areas. Refactor into a proper Next.js App Router layout with: public routes (`/`, `/login`, `/register`) and protected routes (`/dashboard`, `/estimates/*`) guarded by an auth middleware (see NEW-AUTH-01).

### 7.10 Platform & Infrastructure

- **IMP-INF-01** Move sessions out of process memory ([session.py](backend/app/api/state/session.py)) into Redis or PostgreSQL so multiple workers and restarts are safe.
- **IMP-INF-02** Wire the existing Celery stubs ([backend/app/worker/tasks/](backend/app/worker/tasks)) into Docker Compose for background execution of long pipelines.
- **IMP-INF-03** Replace the unconditional development LLM mock ([openrouter_client.py](backend/infrastructure/integrations/openrouter_client.py)) with a feature flag so missing API keys produce a clear error rather than a silent useless estimate.

---

## 8. New Functional Requirements to Be Implemented

These are capabilities **not yet present** in the codebase that are required for an accurate BOQ and a production-ready user experience.

### 8.1 Landing Page

The system currently has no public-facing page. Users who navigate to `/` immediately land on the wizard with no context about what the tool does, who it is for, or how to get started.

- **NEW-LAND-01** Create a dedicated landing page at route `/` (Next.js App Router). The wizard moves to `/estimate/new`.
- **NEW-LAND-02** Landing page sections:
  - **Hero** — headline, sub-headline, primary CTA ("Start Free Estimate" → `/estimate/new`), secondary CTA ("Sign In" → `/login`). Include a screenshot or short GIF of the results page.
  - **How It Works** — three-step visual (Fill Wizard → AI Generates BOQ → Download Excel) with icons.
  - **Feature Highlights** — cards covering: multi-floor wizard, floorplan upload & CV, BSR 2025 rate matching, confidence score, Excel export.
  - **Supported Building Types** — residential, commercial, industrial tiles with representative images.
  - **Testimonials / Use Cases** — placeholder for QS reviewer quotes.
  - **Footer** — links to About, Contact, and Terms.
- **NEW-LAND-03** Landing page is fully responsive (mobile, tablet, desktop) and passes Lighthouse performance score ≥ 90.
- **NEW-LAND-04** Landing page is publicly accessible without authentication; all other application routes (`/dashboard`, `/estimates/*`, `/estimate/new`) require a valid session.

---

### 8.2 Authentication

The system currently has no user accounts. Any person with the URL can run unlimited estimates and there is no way to retrieve a past estimate. Authentication will be implemented using **NextAuth.js (Auth.js v5)** with a `credentials` provider backed by PostgreSQL.

#### 8.2.1 Library & Configuration

- **NEW-AUTH-01** Install `next-auth@5` (Auth.js v5). Create the auth configuration in `frontend/src/auth.ts`:
  ```ts
  import NextAuth from "next-auth";
  import Credentials from "next-auth/providers/credentials";

  export const { handlers, signIn, signOut, auth } = NextAuth({
    providers: [
      Credentials({
        credentials: {
          email:    { label: "Email",    type: "email" },
          password: { label: "Password", type: "password" },
        },
        authorize: async ({ email, password }) => {
          // POST to backend /api/auth/login → returns user or null
        },
      }),
    ],
    session: { strategy: "jwt", maxAge: 7 * 24 * 60 * 60 }, // 7 days
    callbacks: {
      jwt({ token, user }) { if (user) token.role = user.role; return token; },
      session({ session, token }) { session.user.role = token.role; return session; },
    },
    pages: { signIn: "/login", error: "/login" },
  });
  ```
- **NEW-AUTH-02** Mount the NextAuth route handler in `frontend/src/app/api/auth/[...nextauth]/route.ts`:
  ```ts
  export { handlers as GET, handlers as POST } from "@/auth";
  ```
- **NEW-AUTH-03** Add `AUTH_SECRET` (minimum 32 characters, generated with `openssl rand -hex 32`) to `.env.local`. This secret signs the JWT session token.

#### 8.2.2 Middleware & Route Protection

- **NEW-AUTH-04** Create `frontend/src/middleware.ts` using NextAuth's `auth` export as the middleware function. The matcher config protects all routes under `/dashboard`, `/estimates`, `/estimate`, and `/profile`:
  ```ts
  export { auth as middleware } from "@/auth";
  export const config = {
    matcher: ["/dashboard/:path*", "/estimates/:path*", "/estimate/:path*", "/profile/:path*"],
  };
  ```
  Unauthenticated requests to matched routes are automatically redirected to `/login`.

#### 8.2.3 Frontend Pages

- **NEW-AUTH-05** `GET /login` — sign-in page (`frontend/src/app/login/page.tsx`):
  - Email + password form calling `signIn("credentials", { email, password, redirectTo: "/dashboard" })`.
  - Inline error display for `CredentialsSignin` error codes.
  - Links: "Forgot password" → `/forgot-password`, "Create account" → `/register`.
- **NEW-AUTH-06** `GET /register` — registration page (`frontend/src/app/register/page.tsx`):
  - Fields: name, email, password, confirm password, role (Homeowner / QS Engineer / Contractor).
  - Calls `POST /api/users/register` (backend endpoint) then `signIn("credentials", ...)` on success.
- **NEW-AUTH-07** `GET /forgot-password` — email input form; calls `POST /api/auth/forgot-password` on the backend which sends a reset link via SMTP.
- **NEW-AUTH-08** `GET /reset-password?token=...` — new password form; calls `POST /api/auth/reset-password` with the token and new password.
- **NEW-AUTH-09** Sign-out: call `signOut({ redirectTo: "/" })` from a server action or client button; NextAuth clears the session cookie.

#### 8.2.4 Backend: Auth Endpoints (FastAPI)

- **NEW-AUTH-10** `POST /api/users/register` — accepts `{name, email, password, role}`, hashes password with `bcrypt` (cost ≥ 12), inserts into `users` table, returns `{id, name, email, role}`.
- **NEW-AUTH-11** `POST /api/auth/login` — called by the NextAuth `authorize` callback; verifies `bcrypt.checkpw(password, hashed_password)` and returns the user object on success or raises `401`.
- **NEW-AUTH-12** `POST /api/auth/forgot-password` — generates a signed time-limited reset token (24 h expiry), stores a hash in `password_reset_tokens` table, emails the reset link via SMTP (`SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASS` env vars).
- **NEW-AUTH-13** `POST /api/auth/reset-password` — validates token, updates `hashed_password`, invalidates the token row.
- **NEW-AUTH-14** All protected FastAPI routes (`/api/estimates/*`, `/api/estimate-project/*`) validate the authenticated NextAuth session / JWT from the HTTP-only session cookie, not from a Bearer header. Implement this as a FastAPI dependency such as `get_current_user(request: Request)` that:
  - Reads the session token from the cookie attached to the request.
  - Verifies it using `python-jose` or `PyJWT` with `AUTH_SECRET`, or preferably an RS256 public key.
  - Extracts `sub` (user id) and `role` from claims.
  - Returns `401` if the cookie is missing, expired, or invalid.
  - Supports the estimation SSE route (`/api/estimate-project/form/stream/{session_id}`), which must remain cookie-authenticated because native `EventSource` cannot attach a Bearer `Authorization` header.
  - Requires frontend requests to the backend API to send credentials; for cross-origin development this means `fetch(..., { credentials: "include" })` and `new EventSource(url, { withCredentials: true })`, or alternatively serving frontend and backend behind a same-origin reverse proxy.
  - **Security note:** sharing a single symmetric secret between Next.js and FastAPI means a leak from either process compromises both. For production, prefer **RS256 (asymmetric signing)**: NextAuth signs JWTs with a private key; FastAPI holds only the corresponding public key for verification. If symmetric HS256 is used, the `AUTH_SECRET` must be treated as a high-value credential stored exclusively in server-side environment variables, never in client-accessible configuration.

#### 8.2.5 Database Schema

- **NEW-AUTH-15** PostgreSQL tables:
  ```sql
  CREATE TABLE users (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name              TEXT NOT NULL,
    email             TEXT NOT NULL UNIQUE,
    hashed_password   TEXT NOT NULL,
    role              TEXT NOT NULL DEFAULT 'homeowner',  -- homeowner | qs_engineer | contractor
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_login_at     TIMESTAMPTZ
  );

  CREATE TABLE password_reset_tokens (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash  TEXT NOT NULL,
    expires_at  TIMESTAMPTZ NOT NULL,
    used        BOOLEAN NOT NULL DEFAULT false
  );
  ```
- **NEW-AUTH-16** Alembic migration created for both tables.

#### 8.2.6 Security

- **NEW-AUTH-17** Rate-limit `POST /api/users/register` and `POST /api/auth/login` to **5 requests / minute** per IP using `slowapi` (FastAPI rate-limiting middleware). Additionally, lock the account for 15 minutes after 5 consecutive failed login attempts for the same email address. (10 req/min is too permissive — it permits ≈600 password-guess attempts per hour from a single IP.)
- **NEW-AUTH-18** NextAuth JWT is stored in an HTTP-only, `SameSite=Lax`, `Secure` (in production) cookie — inaccessible to JavaScript, mitigating XSS token theft.
- **NEW-AUTH-19** CSRF protection: Auth.js v5 includes built-in CSRF token validation on all `POST /api/auth/*` calls; no additional library is needed for the Auth.js routes. Because protected FastAPI routes will also rely on cookie-backed authentication (see NEW-AUTH-14), state-mutating FastAPI endpoints must implement their own CSRF defense as well, for example a double-submit cookie or a signed CSRF token sent in an `X-CSRF-Token` header on every non-GET request. `SameSite=Lax` helps but is not the sole protection.

---

### 8.3 Dashboard & Estimate Management

After login the user lands on a dashboard. Currently there is no concept of saved estimates.

#### 8.3.1 Dashboard Home (`/dashboard`)

- **NEW-DASH-01** Summary header cards:
  - Total estimates created.
  - Estimates this month.
  - Average confidence score across all estimates.
  - Total estimated value (LKR) across all estimates.
- **NEW-DASH-02** Recent Estimates table (last 10) with columns: Project Name, Building Type, Floors, Total Cost (LKR), Confidence, Status (In Progress / Completed / Failed), Created At, Actions.
- **NEW-DASH-03** Quick-action buttons: **New Estimate** (→ `/estimate/new`), **View All Estimates** (→ `/estimates`).
- **NEW-DASH-04** Sidebar navigation with links: Dashboard, My Estimates, New Estimate, Profile, Sign Out.

#### 8.3.2 Estimate List (`/estimates`)

- **NEW-DASH-05** Paginated, searchable list of all estimates belonging to the authenticated user.
- **NEW-DASH-06** Columns: Project Name, Building Type, Floors, Area (m²), Status, Confidence Score, Grand Total (LKR), Created At, Actions (View, Download Excel, Delete).
- **NEW-DASH-07** Filters: Building Type, Status, Date Range, Confidence Score range.
- **NEW-DASH-08** Bulk-delete selected estimates with a confirmation dialog.

#### 8.3.3 Estimate Detail (`/estimates/[id]`)

- **NEW-DASH-09** Full-page view of a single completed estimate, identical in layout to the current results page but persistent — the user can return to it any time without re-running the pipeline.
- **NEW-DASH-10** Includes:
  - Three summary cards (Grand Total, Confidence Score, BOQ Items count).
  - Full sortable/filterable BOQ table (IMP-FE-01).
  - Per-category cost breakdown chart (IMP-FE-07).
  - Confidence score breakdown card (NEW-CONF-01).
  - Download Excel button (re-generates client-side from stored JSON).
  - Edit mode toggle (IMP-FE-04 / NEW-EDIT-01) with Recompute button.
- **NEW-DASH-11** Estimate metadata editable by the user: project name/label, notes field.
- **NEW-DASH-12** "Duplicate Estimate" action — copies the project_info to a new wizard session pre-filled with the same parameters.

#### 8.3.4 Backend: Estimate Persistence

- **NEW-DASH-13** New PostgreSQL table:
  ```
  estimates (
    id            UUID PRIMARY KEY,
    user_id       UUID REFERENCES users(id) ON DELETE CASCADE,
    project_name  TEXT,
    notes         TEXT,
    status        TEXT,          -- in_progress | completed | failed
    project_info  JSONB,
    result        JSONB,         -- full pipeline output
    confidence    FLOAT,
    grand_total   FLOAT,
    item_count    INTEGER,
    created_at    TIMESTAMPTZ,
    updated_at    TIMESTAMPTZ
  )
  ```
- **NEW-DASH-14** Pipeline writes the completed result JSONB to this table at the end of Stage 11. In-progress status is written when the session is created.
- **NEW-DASH-15** Backend CRUD endpoints:
  - `GET /api/estimates` — paginated list for the authenticated user.
  - `GET /api/estimates/{id}` — single estimate detail.
  - `PATCH /api/estimates/{id}` — update `project_name`, `notes`.
  - `DELETE /api/estimates/{id}` — soft-delete.
  - `POST /api/estimates/{id}/duplicate` — clone project_info into a new session.
- **NEW-DASH-16** All estimate endpoints enforce ownership: a user can only read/write their own estimates. Return `403 Forbidden` for cross-user access.

#### 8.3.5 User Profile (`/profile`)

- **NEW-DASH-17** Profile page: display name, email (read-only), role, change-password form, account deletion.
- **NEW-DASH-18** Account deletion triggers a cascade delete of all associated estimates (enforced by `ON DELETE CASCADE` on the DB FK).

---

### 8.4 Mandatory-Section Template Engine

- **NEW-TPL-01** A configurable `building_type → mandatory sections → minimum item counts` matrix (YAML/JSON) checked into the repo.
- **NEW-TPL-02** A post-LLM enforcer that, after reconciliation, calls a section-specific LLM "expand" prompt for any deficient section.
- **NEW-TPL-03** A test fixture with a "golden" residential BOQ (≥ 150 items) used for regression testing.

### 8.5 BOQ Refinement Loop (Self-Critique)

- **NEW-LOOP-01** After the first reconciliation, run a **QS-critic LLM pass** that scores the BOQ for completeness against the project description and returns a list of missing items.
- **NEW-LOOP-02** Loop up to N (configurable, default 2) until either no missing items are reported or a max iteration count is reached.
- **NEW-LOOP-03** Persist the critic's findings in the audit log and the final report.

### 8.6 Per-Floor BOQ Expansion

- **NEW-FLOOR-01** A deterministic post-processor that, for each floor in `project_info.floor_areas`, instantiates copies of category items whose nature is per-floor (concrete, masonry, plaster, painting, flooring, electrical points).
- **NEW-FLOOR-02** Per-floor items inherit `floor_label` (`GF`, `FF`, `SF`, ...) and per-floor area from the wizard; quantities are recomputed using floor-specific area.

### 8.7 Schedule Generators

- **NEW-SCH-01** Door schedule generator: from `opening_count` and zone labels, produce one BOQ item per door type (main, internal, bathroom, kitchen) × location.
- **NEW-SCH-02** Window schedule generator (analogous).
- **NEW-SCH-03** Sanitary schedule generator: from `bathrooms × floors`, produce WC, basin, shower mixer, floor trap, soap holder, etc.
- **NEW-SCH-04** Electrical schedule generator: points per room type (lighting, switch, socket, fan), DB count, conduit length.

### 8.8 BSR Coverage Audit

- **NEW-BSR-01** Pre-startup audit that reports the % of BSR sections represented in the vector store; alerts if a section is missing.
- **NEW-BSR-02** Endpoint `GET /api/bsr/coverage` returning sections, item counts, last ingest timestamp.

### 8.9 Edit-and-Recompute UI

- **NEW-EDIT-01** Frontend allows the QS to edit quantity / rate / unit / description of any BOQ item.
- **NEW-EDIT-02** Backend endpoint `POST /api/estimate-project/recompute` recomputes costs and confidence from edited items without re-running the LLM stages.

### 8.10 Rate Limiting & Security Hardening

- **NEW-SEC-01** Cookie-backed authenticated session enforcement on all `/api/estimate-project/*` and `/api/estimates/*` routes, implemented by the backend dependency in **NEW-AUTH-14**. This is **not** fulfilled by **NEW-AUTH-04** alone; Next.js middleware protects frontend pages, while FastAPI routes require their own backend authentication check.
- **NEW-SEC-02** Per-user rate limit (token-bucket, 5 estimates / hour) on `POST /api/estimate-project/form/submit` — protects the OpenRouter and ML inference budget.
- **NEW-SEC-03** Per-user project history in PostgreSQL (fulfilled by NEW-DASH-13).
- **NEW-SEC-04** CSRF protection on all state-mutating API routes when using cookie-based sessions.
- **NEW-SEC-05** Content-Security-Policy and HSTS headers added to the Next.js `next.config.ts`.

### 8.11 Region & Currency Localisation

- **NEW-LOC-01** Region selector at intake; backend applies regional rate factor.
- **NEW-LOC-02** Currency formatting at the API boundary.

### 8.12 PDF Export

- **NEW-PDF-01** Print-ready PDF report with cover page, project summary, BOQ, signatures area.

### 8.13 Test Suite Expansion

- **NEW-TEST-01** Golden-output regression tests (one per building type) that lock minimum item count, mandatory categories, and price-per-m² band.
- **NEW-TEST-02** Property-based tests for quantity calculator (units, dimensionality).
- **NEW-TEST-03** End-to-end integration test that runs the wizard → SSE → result with a stub LLM.
- **NEW-TEST-04** Authentication flow tests: registration, login, logout, password reset, protected route guard.
- **NEW-TEST-05** Dashboard CRUD tests: create estimate, list estimates, view detail, duplicate, delete.

---

## 9. Confidence-Score Improvement Plan

### 9.1 Current effective floor

With the current model, a typical residential run scores 0.20-0.40 because:

- baseline starts at 0.50,
- defaults penalty ~0.10-0.20,
- unmatched fraction penalty 0.10-0.30 (LLM phrasing mismatch),
- no coverage credit.

### 9.2 Target

- Median residential confidence ≥ **0.75**.
- Confidence ≥ 0.85 when both wizard parameters and floorplan are provided **and** all mandatory categories are covered.

### 9.3 Levers (from sections 7 & 8)

1. **IMP-CONF-01**: stop counting contractual items as unmatched → +~0.05 typical.
2. **IMP-CONF-02 / NEW-TPL-02**: add coverage bonus once all mandatory sections are present → +0.15.
3. **IMP-RAG-01 / IMP-RAG-03**: improve match rate from ~50 % to ~85 % → +~0.15.
4. **IMP-QTY-02 / IMP-QTY-03**: eliminate unit mismatches and runaway quantities → fewer validation warnings → +~0.05.
5. **IMP-CV-01**: replace square-perimeter heuristic → raises geometry confidence → +~0.05.

### 9.4 Reporting

- **NEW-CONF-01** Surface a **breakdown card** in the UI: "+0.10 floorplan, +0.15 coverage, −0.05 defaults applied, ..." so the user understands the score.

---

## 10. Acceptance Criteria & Target KPIs

### 10.1 Estimation Quality

| KPI | Current (per attached screenshot) | Target |
|---|---|---|
| BOQ item count for a 2-storey residence | 25 | ≥ 120 |
| Mandatory section coverage | unmeasured | 100 % of mandatory sections present |
| BSR `confirmed` match rate | ~50 % (estimated) | ≥ 85 % |
| Items with `match_type = no_match` | unknown | ≤ 5 % |
| Median confidence (residential, full intake) | 0.20-0.40 | ≥ 0.75 |
| Cost / m² sanity-check pass rate | unmeasured | ≥ 95 % |
| End-to-end pipeline latency (residence) | ~30-60 s | ≤ 90 s with new loop |
| Excel report download | partial | full per IMP-REP-01 |
| PDF report download | not implemented | shipped per NEW-PDF-01 |

### 10.2 Frontend / UX

| KPI | Current | Target |
|---|---|---|
| Landing page | None — wizard loads at `/` | Public landing page at `/` with hero, features, CTAs |
| Authentication | None | Email + password login/register; protected routes |
| Saved estimates | None — result lost on page refresh | All completed estimates persisted; accessible via dashboard |
| Dashboard | None | `/dashboard` with summary cards + recent estimates table |
| Estimate list | None | `/estimates` with search, filter, pagination |
| Estimate detail (persistent) | None | `/estimates/[id]` — full BOQ table, charts, download, edit |
| Results BOQ table | Top 5 preview rows only | Full sortable/filterable table |
| Confidence breakdown visible | No | Score breakdown card (NEW-CONF-01) |
| Cost breakdown chart | No | Bar/pie chart from `costs.subtotals` |
| Lighthouse performance score (landing) | N/A | ≥ 90 |
| Mobile responsiveness | Partial (Tailwind) | All pages fully responsive |

---

## 11. Out of Scope

- Retraining or replacing `item_predictor.joblib` and `quantity_predictor.joblib` on new datasets (covered by a separate ML plan).
- Real-time collaborative editing of the BOQ.
- Procurement, scheduling, or progress-tracking workflows.
- Mobile-native applications.
- Multi-language UI.
- OAuth / social login providers (Google, GitHub, etc.) — only email + password credentials via NextAuth.js v5 is in scope.
- Hosted auth providers (Clerk, Supabase Auth, Auth0) — all auth is self-hosted using NextAuth.js v5 + PostgreSQL.

---

## 12. Glossary

| Term | Definition |
|---|---|
| **BOQ** | Bill of Quantities — itemised list of construction work with quantities. |
| **BSR** | Bill of Schedule of Rates — Sri Lankan government rate book (Western Province 2025). |
| **MVED** | Minimum Viable Estimation Data — the seven required project fields. |
| **RAG** | Retrieval-Augmented Generation — vector retrieval + scoring used to map BOQ descriptions to BSR records. |
| **SSE** | Server-Sent Events — one-way event stream used for live pipeline progress. |
| **Soft match** | RAG result with score in [0.30, 0.45) — best-effort match flagged for review. |
| **Confirmed match** | RAG result with score ≥ 0.45. |
| **Item Predictor** | Random-Forest multi-output classifier predicting required work categories. |
| **Quantity Predictor** | Regression model predicting quantities (log1p target). |
| **Geometry confidence** | Floorplan CV self-rating in [0, 1]. |
| **Coverage** | Fraction of mandatory categories represented in the final BOQ. |

---

*End of document.*

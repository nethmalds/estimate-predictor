# Service Module Encapsulation — Full Implementation Plan

## Architectural Rule

Every `backend/services/<module>/` directory must follow this contract:

1. **`service.py`** — the sole external interface. Contains only re-exports and thin wrapper methods that inject internal dependencies. Zero business logic.
2. **All other `.py` files** — contain all business logic, math, algorithms, and domain rules. Never imported directly by code outside the module.
3. **No business logic** may live outside `backend/services/` (not in `application/`, not in `app/api/controllers/`, not in `app/worker/tasks/`).

---

## Part A — Previously Completed (Phase 1 & 2 of the encapsulation fix)

These items were already implemented. Listed for completeness.

### A1 — Created missing `service.py` facades

| Module | Action | Exports Added |
|---|---|---|
| `pricing_process/` | Created `service.py` (was placeholder) | `calculate_costs`, `resolve_rate` |
| `reporting_process/` | Created `service.py` (did not exist) | `build_report`, `generate_excel_report` |
| `validation/` | Created `service.py` (did not exist) | `validate_boq_items`, `score_confidence`, `validate_quantities` |

### A2 — Extended incomplete facades

| Module | Exports Added |
|---|---|
| `rag_process/service.py` | `init_db`, `extract_query_features`, `clean_boq_query` |
| `clarification_process/service.py` | `normalize_wizard_to_project_info`, `validate_wizard_payload` |
| `floorplan_process/service.py` | `compute_geometry_confidence` |

### A3 — Fixed external callers that bypassed facades

| File | Fix Applied |
|---|---|
| `app/api/controllers/estimation_controller.py` | Merged `retriever` + `scorer` imports into `rag_process.service` |
| `app/api/server.py` | `init_db` now from `rag_process.service` |
| `app/api/controllers/form_controller.py` | `clarification_agent` imports now from `clarification_process.service` |
| `application/pipelines/estimation_pipeline.py` | All 6 direct inner-module imports replaced with service facades |
| `application/floorplan/confidence_scorer.py` | Now re-exports through `floorplan_process.service` |

---

## Part B — Outstanding Work (Misplaced Logic Outside Service Modules)

### Audit Findings

Four business-logic functions currently reside **outside** `backend/services/`:

| Function | Current Location | Belongs In |
|---|---|---|
| `_is_contractual_item(item)` | `application/pipelines/estimation_pipeline.py` L217 | `services/rag_process/matcher.py` |
| `_match_bsr_items(items, cb)` | `application/pipelines/estimation_pipeline.py` L226 | `services/rag_process/matcher.py` |
| `_build_source_summary(items)` | `application/pipelines/estimation_pipeline.py` L289 | `services/reporting_process/source_summarizer.py` |
| `_merge_floorplan_geometries(geometries)` | `application/pipelines/estimation_pipeline.py` L363 | `services/floorplan_process/geometry_merger.py` |
| Inline scoring logic in `diagnose_bsr()` | `app/api/controllers/estimation_controller.py` L60–115 | `services/rag_process/diagnostics.py` |

One additional issue:

| File | Problem |
|---|---|
| `app/worker/tasks/estimation_tasks.py` | Imports `run_estimation_pipeline` which does not exist (broken at runtime). Function is `run_estimation_pipeline_from_project_info`. |
| `tests/unit/test_floorplan_merge.py` | Imports `_merge_floorplan_geometries` directly from the pipeline — must update after function moves |
| `application/floorplan/confidence_scorer.py` | Deprecated stub. Zero importers. Dead code — delete. |

---

## Part B — Implementation Plan

### Phase 1 — Create new logic files inside the correct service modules

---

#### Step 1 — `backend/services/rag_process/matcher.py` *(CREATE)*

Contains: `is_contractual_item` and `match_boq_items_batch`.

`match_boq_items_batch` receives a `match_one_fn` parameter (the per-item RAG call) to avoid a circular import with `service.py`.

```python
"""BSR item matching logic — batch matching and contractual item classification."""
from __future__ import annotations

_CONTRACTUAL_KEYWORDS = {
    "performance security",
    "advance payment security",
    "advance payment bond",
    "advance bond",
    "lump sum",
}


def is_contractual_item(item: dict) -> bool:
    """Return True for financial/contractual items that cannot be BSR-matched."""
    desc = (item.get("description") or "").lower()
    cat  = (item.get("category") or "").lower()
    if cat == "preliminary_and_general":
        return True
    return any(kw in desc for kw in _CONTRACTUAL_KEYWORDS)


def match_boq_items_batch(items: list[dict], match_one_fn) -> list[dict]:
    """Match every BOQ item against BSR, skipping contractual items.

    Parameters
    ----------
    items:
        Raw BOQ items to match.
    match_one_fn:
        Callable[[str], dict] — single-item RAG match function, injected
        by service.py to avoid circular imports.
    """
    matched: list[dict] = []

    for item in items:
        description = item.get("description") or ""

        if is_contractual_item(item):
            merged = dict(item)
            merged.update({
                "bsr_item_no":    "CONTRACTUAL",
                "bsr_description": None,
                "unit":            "item",
                "rate":            0.0,
                "match_confidence": 0.0,
                "match_type":      "contractual",
                "needs_rate_review": True,
            })
            matched.append(merged)
            continue

        bsr_match = match_one_fn(description)
        merged = dict(item)
        merged.update({
            "bsr_item_no":      bsr_match.get("item_no"),
            "bsr_description":  bsr_match.get("description"),
            "unit":             bsr_match.get("unit"),
            "rate":             bsr_match.get("rate") or 0.0,
            "match_confidence": bsr_match.get("confidence"),
            "match_type":       bsr_match.get("match_type", "no_match"),
            "needs_rate_review": bsr_match.get("needs_rate_review", False),
        })
        matched.append(merged)

    return matched
```

---

#### Step 2 — `backend/services/rag_process/diagnostics.py` *(CREATE)*

Contains: `diagnose_boq_items` — the scoring logic currently embedded in `estimation_controller.py::diagnose_bsr()`.

```python
"""RAG diagnostic logic — detailed BSR candidate scoring for dev/QA endpoints."""
from __future__ import annotations

from sqlalchemy.orm import Session

from services.rag_process.retriever import (
    extract_query_features,
    clean_boq_query,
    retrieve_candidates,
)
from services.rag_process.scorer import score_candidate
from core.config.settings import settings


def diagnose_boq_items(
    descriptions: list[str],
    top_k: int,
    db: Session,
    vector_store,
    embedder,
) -> dict:
    """Return detailed BSR candidate scoring for each description.

    Used by the /api/rag/diagnose dev endpoint.
    """
    SOFT    = 0.30
    CONFIRM = settings.min_confidence_threshold

    results = []
    for desc in descriptions:
        query_features = extract_query_features(desc)
        cleaned_text   = clean_boq_query(query_features.normalized_text)

        query_features_obj, candidates = retrieve_candidates(
            boq_text=desc,
            session=db,
            vector_store=vector_store,
            embedder=embedder,
            top_k=top_k,
        )

        scored_candidates = []
        for cand in candidates:
            bsr_item = cand["bsr_item"]
            scores   = score_candidate(query_features_obj, bsr_item, cand["vector_score"])
            fs = scores["final_score"]
            mt = "no_match" if fs < SOFT else ("soft_match" if fs < CONFIRM else "confirmed")
            scored_candidates.append({
                "item_no":         bsr_item.item_no,
                "bsr_description": bsr_item.description,
                "unit":            bsr_item.unit,
                "rate":            bsr_item.rate,
                "vector_score":    scores["vector_score"],
                "keyword_score":   scores["keyword_score"],
                "final_score":     scores["final_score"],
                "match_type":      mt,
                "matched_fields":  scores["matched_fields"],
            })

        scored_candidates.sort(key=lambda x: x["final_score"], reverse=True)
        results.append({
            "description":        desc,
            "cleaned_text":       cleaned_text,
            "detected_work_type": query_features.work_type,
            "detected_material":  query_features.material,
            "top_candidates":     scored_candidates,
        })

    return {"count": len(results), "results": results}
```

---

#### Step 3 — `backend/services/reporting_process/source_summarizer.py` *(CREATE)*

Contains: `build_source_summary` — the transparency-layer bucketing logic currently in the pipeline.

```python
"""Source attribution summarizer — counts BOQ items by their quantity source type."""
from __future__ import annotations

_DISCRETE_UNITS = frozenset({"nr", "nr.", "no", "no.", "item", "pair", "set", "each", "lot"})


def build_source_summary(items: list[dict]) -> dict:
    """Count items by source type for transparency reporting.

    Buckets
    -------
    geometry_only, parametric_only, ml_only, fused,
    globally_allocated, low_confidence, discretely_rounded, unknown
    """
    summary: dict[str, int] = {
        "geometry_only":      0,
        "parametric_only":    0,
        "ml_only":            0,
        "fused":              0,
        "globally_allocated": 0,
        "low_confidence":     0,
        "discretely_rounded": 0,
        "unknown":            0,
    }

    for item in items:
        candidates     = item.get("quantity_candidates") or []
        recon          = item.get("reconciliation_summary") or {}
        review_flags   = recon.get("review_flags") or []
        candidate_count = recon.get("candidate_count") or len(candidates)
        source = item.get("quantity_source") or "unknown"
        unit   = str(item.get("unit") or item.get("preferred_unit") or "").lower().strip()
        conf   = float(item.get("quantity_confidence") or item.get("quantity_confidence_score") or 0.0)

        if unit in _DISCRETE_UNITS:
            summary["discretely_rounded"] += 1
        if conf < 0.50:
            summary["low_confidence"] += 1

        if "global_allocation_only" in review_flags or "global_allocation_used" in review_flags:
            summary["globally_allocated"] += 1
            continue

        if candidate_count >= 2:
            summary["fused"] += 1
            continue

        cand_types = [c.get("candidate_type", "") for c in candidates] if candidates else [source]
        if any(t in ("geometry", "rule_based") for t in cand_types):
            summary["geometry_only"] += 1
        elif any(t == "parametric" for t in cand_types):
            summary["parametric_only"] += 1
        elif any(t in ("ml_item_level", "quantity_predictor") for t in cand_types):
            summary["ml_only"] += 1
        else:
            summary["unknown"] += 1

    return summary
```

---

#### Step 4 — `backend/services/floorplan_process/geometry_merger.py` *(CREATE)*

Contains: `merge_floorplan_geometries` — the multi-image aggregation logic currently in the pipeline.

```python
"""Floorplan geometry merger — aggregates results from multiple floorplan images."""
from __future__ import annotations

_SCALE_PRIORITY = ["ocr_confirmed", "ocr_dimensions", "detector", "heuristic"]


def merge_floorplan_geometries(geometries: list[dict]) -> dict:
    """Merge geometry dicts from multiple floorplan images into one aggregate.

    Strategy: totals summed, confidence weighted-averaged,
    scale source = most reliable, heuristic flags OR-ed, rooms concatenated.
    """
    if not geometries:
        return {}
    if len(geometries) == 1:
        return geometries[0]

    total_area      = sum(g.get("total_floor_area_m2", 0.0) for g in geometries)
    total_perimeter = sum(g.get("perimeter_m", 0.0) for g in geometries)
    total_walls     = sum(g.get("wall_length_m", 0.0) for g in geometries)
    total_openings  = sum(g.get("opening_count", 0) for g in geometries)
    total_rooms     = sum(g.get("room_count", 0) for g in geometries)
    all_rooms       = [r for g in geometries for r in (g.get("rooms") or [])]

    confs    = [float(g.get("geometry_confidence", 0.0)) for g in geometries]
    avg_conf = sum(confs) / len(confs)

    best_scale = min(
        (g.get("scale_source", "heuristic") for g in geometries),
        key=lambda s: _SCALE_PRIORITY.index(s) if s in _SCALE_PRIORITY else 99,
    )

    _FLAG_KEYS = (
        "derived_from_area_only",
        "assumed_floor_height",
        "inferred_internal_walls",
        "missing_scale_confirmation",
    )
    merged_flags: dict[str, bool] = {
        key: any(g.get("heuristic_flags", {}).get(key, False) for g in geometries)
        for key in _FLAG_KEYS
    }

    return {
        "total_floor_area_m2": round(total_area, 2),
        "perimeter_m":         round(total_perimeter, 2),
        "wall_length_m":       round(total_walls, 2),
        "opening_count":       total_openings,
        "room_count":          total_rooms,
        "rooms":               all_rooms,
        "geometry_confidence": round(avg_conf, 4),
        "scale_source":        best_scale,
        "heuristic_flags":     merged_flags,
        "method":              "multi_image_merged",
        "source_count":        len(geometries),
        "inferred_area_flag":  any(g.get("inferred_area_flag", False) for g in geometries),
    }
```

---

### Phase 2 — Extend the three service.py facades

---

#### Step 5 — `backend/services/floorplan_process/service.py` *(EXTEND)*

Add re-export of `merge_floorplan_geometries`:

```python
# Add to existing imports:
from services.floorplan_process.geometry_merger import merge_floorplan_geometries
```

---

#### Step 6 — `backend/services/reporting_process/service.py` *(EXTEND)*

Add re-export of `build_source_summary`:

```python
# Add to existing imports:
from services.reporting_process.source_summarizer import build_source_summary

# Add to __all__:
"build_source_summary",
```

---

#### Step 7 — `backend/services/rag_process/service.py` *(EXTEND)*

Add two wrapper methods to `BOQMatcherService` that inject internal state into the pure-function modules:

```python
# Add to imports at top of file:
from services.rag_process.matcher import match_boq_items_batch as _match_boq_items_batch
from services.rag_process.diagnostics import diagnose_boq_items as _diagnose_boq_items

# Add to BOQMatcherService class body:
def match_boq_items_batch(self, items: list[dict]) -> list[dict]:
    """Batch-match BOQ items against BSR, skipping contractual items."""
    return _match_boq_items_batch(items, self.match_boq_item)

def diagnose_boq_items(self, descriptions: list[str], top_k: int, db) -> dict:
    """Return detailed BSR candidate scoring for dev/QA diagnostics."""
    return _diagnose_boq_items(
        descriptions,
        top_k,
        db,
        self._get_vector_store(),
        self._get_embedder(),
    )
```

---

### Phase 3 — Update callers to use the new service methods

---

#### Step 8 — `backend/application/pipelines/estimation_pipeline.py` *(MODIFY)*

**Imports — add:**
```python
from services.floorplan_process.service import merge_floorplan_geometries as _merge_floorplan_geometries
from services.reporting_process.service import build_source_summary as _build_source_summary
```

**Call sites — update (3 lines, no logic change, just rename):**
- `_merge_floorplan_geometries(geometries)` → already aliased above, no change needed to call sites
- `_match_bsr_items(boq_items, progress_callback)` → `rag_service.match_boq_items_batch(boq_items)`
- `_build_source_summary(boq_items)` → already aliased above, no change needed to call sites

**Remove (four helper definitions + two module-level constants):**
- `_CONTRACTUAL_KEYWORDS` set (line ~215)
- `_is_contractual_item()` function (line ~217)
- `_match_bsr_items()` function (line ~226)
- `_build_source_summary()` function (line ~289)
- `_SCALE_PRIORITY` list (line ~363)
- `_merge_floorplan_geometries()` function (line ~366)

After this change the pipeline file contains **zero business logic** — only orchestration, service calls, and progress event emission.

---

#### Step 9 — `backend/app/api/controllers/estimation_controller.py` *(MODIFY)*

Replace the entire body of `diagnose_bsr()` with a single service call:

```python
def diagnose_bsr(payload: DiagnoseRequest, db: Session = Depends(get_db_session)):
    try:
        return service.diagnose_boq_items(payload.descriptions, payload.top_k, db)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
```

Remove now-unused imports:
- `extract_query_features`
- `clean_boq_query`
- `retrieve_candidates`
- `score_candidate`
- `settings` (no longer needed in this file)

---

#### Step 10 — `backend/app/worker/tasks/estimation_tasks.py` *(MODIFY)*

Fix the broken import and wrong function name:

```python
# Before (broken — function does not exist):
from application.pipelines.estimation_pipeline import run_estimation_pipeline

def run_estimation_task(description: str) -> dict:
    return run_estimation_pipeline(description)

# After (correct):
from application.pipelines.estimation_pipeline import run_estimation_pipeline_from_project_info

def run_estimation_task(project_info: dict, floorplan_urls: list[str] | None = None) -> dict:
    return run_estimation_pipeline_from_project_info(project_info, floorplan_urls=floorplan_urls)
```

---

#### Step 11 — `backend/tests/unit/test_floorplan_merge.py` *(MODIFY)*

Update import to use the service facade:

```python
# Before:
from application.pipelines.estimation_pipeline import _merge_floorplan_geometries

# After:
from services.floorplan_process.service import merge_floorplan_geometries as _merge_floorplan_geometries
```

No other changes needed — all call sites use the local alias `_merge_floorplan_geometries` so they continue to work.

---

### Phase 4 — Delete dead code

---

#### Step 12 — Delete `backend/application/floorplan/confidence_scorer.py`

Verified: zero importers anywhere in the codebase. Safe to delete.

Command:
```
del "backend\application\floorplan\confidence_scorer.py"
```

#### Step 13 — Delete empty `backend/application/floorplan/` directory

After step 12 the directory is empty. Remove it.

Command:
```
rmdir "backend\application\floorplan"
```

---

## Files Summary

| File | Action | Reason |
|---|---|---|
| `services/rag_process/matcher.py` | **CREATE** | Houses `is_contractual_item` + `match_boq_items_batch` |
| `services/rag_process/diagnostics.py` | **CREATE** | Houses `diagnose_boq_items` |
| `services/reporting_process/source_summarizer.py` | **CREATE** | Houses `build_source_summary` |
| `services/floorplan_process/geometry_merger.py` | **CREATE** | Houses `merge_floorplan_geometries` |
| `services/rag_process/service.py` | **EXTEND** | Add `match_boq_items_batch` + `diagnose_boq_items` wrapper methods |
| `services/floorplan_process/service.py` | **EXTEND** | Re-export `merge_floorplan_geometries` |
| `services/reporting_process/service.py` | **EXTEND** | Re-export `build_source_summary` |
| `application/pipelines/estimation_pipeline.py` | **MODIFY** | Remove 4 helper definitions; update 1 call site; add 2 imports |
| `app/api/controllers/estimation_controller.py` | **MODIFY** | Replace inline diagnose logic with `service.diagnose_boq_items()` |
| `app/worker/tasks/estimation_tasks.py` | **MODIFY** | Fix broken import + wrong function name |
| `tests/unit/test_floorplan_merge.py` | **MODIFY** | Update import to use service facade |
| `application/floorplan/confidence_scorer.py` | **DELETE** | Dead code — zero importers |
| `application/floorplan/` directory | **DELETE** | Empty after stub removed |

---

## Final State After Implementation

### `backend/services/` structure
```
services/
├── clarification_process/
│   ├── clarification_agent.py   ← business logic
│   ├── llm_client.py            ← business logic
│   └── service.py               ← facade only
├── floorplan_process/
│   ├── confidence_scorer.py     ← business logic
│   ├── geometry_merger.py       ← business logic  (NEW)
│   ├── image_cache.py           ← business logic
│   ├── orchestrator.py          ← business logic
│   ├── service.py               ← facade only
│   └── geometry_extraction/
│       ├── geometry_extractor.py
│       ├── ocr.py
│       └── yolo_detector.py
├── item_gen_process/
│   ├── boq_builder.py           ← business logic
│   ├── item_predictor.py        ← business logic
│   ├── llm_client.py            ← business logic
│   └── service.py               ← facade only
├── pricing_process/
│   ├── cost_calculator.py       ← business logic
│   ├── rate_resolver.py         ← business logic
│   └── service.py               ← facade only
├── quantity_gen_process/
│   ├── confidence_scoring.py    ← business logic
│   ├── quantity_calculator.py   ← business logic
│   ├── quantity_validator.py    ← business logic
│   ├── rule_based_calculator.py ← business logic
│   └── service.py               ← facade only
├── rag_process/
│   ├── db.py                    ← business logic
│   ├── diagnostics.py           ← business logic  (NEW)
│   ├── embeddings.py            ← business logic
│   ├── matcher.py               ← business logic  (NEW)
│   ├── pdf_parser.py            ← business logic
│   ├── retriever.py             ← business logic
│   ├── scorer.py                ← business logic
│   └── service.py               ← facade only
├── reporting_process/
│   ├── excel_generator.py       ← business logic
│   ├── pdf_generator.py         ← business logic
│   ├── report_builder.py        ← business logic
│   ├── source_summarizer.py     ← business logic  (NEW)
│   └── service.py               ← facade only
└── validation/
    ├── boq_validator.py         ← business logic
    ├── confidence_scoring.py    ← business logic
    ├── quantity_validator.py    ← business logic
    └── service.py               ← facade only
```

### `backend/application/` structure (after cleanup)
```
application/
└── pipelines/
    └── estimation_pipeline.py   ← pure orchestration only, zero logic
```

---

## Verification Checklist

After implementation, run these checks:

```bash
# 1. No business-logic functions remain outside services/
grep -rn "def _is_contractual_item\|def _match_bsr_items\|def _build_source_summary\|def _merge_floorplan_geometries" backend/
# Expected: zero matches

# 2. No files in application/ import private pipeline helpers
grep -rn "from application\.floorplan" backend/
# Expected: zero matches

# 3. services/ modules never imported directly from outside (except via service.py)
grep -rn "from services\.[a-z_]*\.[^s][a-z_]* import" backend/app/ backend/application/ backend/tests/
# Expected: zero matches

# 4. Unit tests still pass
pytest backend/tests/unit/test_floorplan_merge.py -v

# 5. Server starts with no import errors
uvicorn app.api.server:app --reload
```

---

## Out of Scope (Deliberate Decisions)

1. **`BOQMatcherService` class in `rag_process/service.py`** — it already lives inside the rag module. Its methods (`match_boq_item`, `bootstrap`, etc.) contain domain logic but are part of the pre-existing class design. Refactoring them into separate files would achieve stricter facade purity but is not required by the rule being enforced here.

2. **`application/pipelines/estimation_pipeline.py` location** — this file orchestrates across 8 service modules. It is architecturally higher-level than any single domain service and cannot belong to one module's `service.py`. It stays at `application/pipelines/`; after this refactor it contains no business logic, only orchestration.

3. **`app/api/controllers/form_controller.py`** — already fixed in Part A. Pure delegation to `application/pipelines/estimation_pipeline.py`. No logic of its own.

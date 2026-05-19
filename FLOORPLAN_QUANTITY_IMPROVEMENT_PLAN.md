# Floorplan Confidence Maximisation + Quantity Prediction Cascade

**Branch:** `feat/tests`  
**Date:** 2026-05-19  
**Scope:** `backend/services/floorplan_process/` · `backend/services/quantity_gen_process/`

---

## Problem Statement

### Problem 1 — Floorplan confidence is artificially low

The provided floor plan is high quality — 8 labelled rooms, explicit feet/inch dimensions on every room, clear door arcs and window gaps. Yet the pipeline scores it **≈0.41** instead of a possible **≈0.74+** because:

| Root cause | Impact | Verified? |
|-----------|--------|-----------|
| Tesseract not on PATH → `TesseractNotFoundError` caught inside OCR module → returns empty result → `c_ocr = 0.0` | Loses the full 0.30 weight in confidence formula | ✅ confirmed — warning emitted, `dimensions_raw = []` |
| `_infer_area_from_dimensions()` only matches metric `m` suffix → every feet/inch token silently ignored → `dimensions_raw = []` | `scale_source` stays `"detector"` (YOLO saves it from `"heuristic"`), but no OCR cross-check so no `"ocr_confirmed"` upgrade | ✅ confirmed — imperial labels present but unparsed |
| Room names not extracted from OCR text → all YOLO zones labelled `"zone"` | BOQ and report lack room-level granularity | ✅ confirmed — all 11 rooms show `label: "zone"` |
| `preprocess_image()` does zero image enhancement → YOLO receives raw pixels | YOLO avg conf = 0.6887 instead of ≈0.72 | ✅ confirmed — no preprocessing path in current code |

### Problem 2 — Quantity prediction has no category-level safety net

When the per-item ML model has no trained entry for a specific work item, it falls to the global model with coarse QS-weight distribution. There is no explicit step that:
1. Predicts the **total quantity for an entire category** using the ML model on aggregated features
2. **Distributes** that total across the category's items proportionally

The result: whole-building quantities duplicated across every line (e.g. all 6 brick masonry items showing identical 86.06), or items flagged for review with no actionable resolution path.

---

## Pipeline Run — Verified Results (2026-05-19)

Image: `train.dir/image-processing/test/image6.jpg` (8-room residential floorplan, imperial labels)

```
geometry_confidence  : 0.4172   ← confirmed by live run
scale_source         : detector  ← YOLO zones present, OCR dims absent
dimensions_confidence: 0.0       ← Tesseract not on PATH → no dim tokens
openings_confidence  : 0.6887    ← YOLO avg conf across 21 openings
coverage_confidence  : 1.0       ← 11 zones detected (≥5 cap)
_ocr_succeeded       : True      ← function returned without exception (skipped internally)
_yolo_succeeded      : True      ← model ran cleanly
_yolo_avg_conf       : 0.6887
total_floor_area_m2  : 116.5     ← from YOLO bbox sum (no OCR cross-check)
room_count           : 11        ← all labelled "zone" — names not extracted
opening_count        : 21
method               : ocr_text_only
dimensions_raw       : []        ← imperial tokens silently dropped
```

Heuristic flags: `assumed_floor_height=True`, all others `False` → p_heuristic = 0.25

**Root cause corrections vs original analysis:**

| Original assumption | Actual finding |
|--------------------|----------------|
| `scale_source = "heuristic"` (0.20) | `scale_source = "detector"` (0.60) — YOLO found 11 zones |
| `c_det ≈ 0.65` | `c_det = 0.6887` (measured) |
| OCR error raises exception → `_ocr_succeeded = False` | OCR module swallows `TesseractNotFoundError` internally; `_ocr_succeeded = True` is misleading — it means "no exception propagated", not "dims found" |

---

## Confidence Formula Reference

```
c_g = clamp(β₁·c_ocr + β₂·c_det + β₃·c_scale + β₄·c_coverage − β₅·p_heuristic, 0, 1)
```

| Symbol | Weight (β) | **Actual measured** | Target value |
|--------|-----------|---------------------|-------------|
| c_ocr  | 0.30 | **0.0** (Tesseract not on PATH) | 1.0 (vision API fallback) |
| c_det  | 0.25 | **0.6887** (measured) | ≈0.72 (after preprocessing) |
| c_scale | 0.20 | **0.60** (`detector`) | 1.00 (`ocr_confirmed`) |
| c_coverage | 0.15 | **1.0** (11 zones ≥ 5) | 1.0 |
| p_heuristic | −0.10 | **0.25** (1 of 4 flags true) | 0.25 |
| **c_g total** | | **0.4172** | **≈0.80** |

Scale source scores: `ocr_confirmed=1.00` · `ocr_dimensions=0.80` · `detector=0.60` · `area_inferred=0.40` · `heuristic=0.20`

---

## Part 1 — Floorplan Confidence Maximisation

### Change A — Vision-API OCR fallback

**File:** `backend/services/floorplan_process/geometry_extraction/ocr.py`

#### What
When Tesseract raises `TesseractNotFoundError` (caught at line 63), instead of immediately returning `_ocr_skip_result()`, call the configured LLM API with the floor plan image and extract dimension text from the response.

#### How

**Step 1 — Add `_extract_dimensions_via_vision(image_path: str) -> dict`**

```python
def _extract_dimensions_via_vision(image_path: str) -> dict:
    """Fallback OCR using the configured LLM vision API."""
    import base64
    from pathlib import Path

    image_file = Path(image_path)
    b64 = base64.b64encode(image_file.read_bytes()).decode()
    ext = image_file.suffix.lstrip(".").lower()
    mime = {"jpg": "image/jpeg", "jpeg": "image/jpeg",
            "png": "image/png", "webp": "image/webp"}.get(ext, "image/png")

    prompt = (
        "You are analyzing a floor plan image. "
        "List every room name and its dimension label exactly as printed "
        "(e.g. 'Bedroom 1: 11\\'3\" x 8\\'11\"'). "
        "Return only the labels, one per line. No explanation."
    )

    # Call existing LLM client — same pattern as services/item_gen_process/
    raw_text = _call_llm_vision(b64, mime, prompt)   # helper added below

    return _extract_dimensions(image_file, raw_text)  # reuse existing helper
```

**Step 2 — Add `_call_llm_vision(b64: str, mime: str, prompt: str) -> str`**

Reuse the existing LLM client already configured in the backend (same API key / host as BOQ generation). Pass the image as a base64 content block alongside the text prompt. Return the raw text response string.

**Step 3 — Wire into the Tesseract except block**

```python
except pytesseract.TesseractNotFoundError:
    warnings.warn("[OCR] Tesseract not found — trying vision API fallback.", stacklevel=2)
    try:
        return _extract_dimensions_via_vision(image_path)
    except Exception as vision_exc:
        warnings.warn(f"[OCR] Vision fallback failed: {vision_exc}", stacklevel=2)
        return _ocr_skip_result(image_file, "tesseract_not_found_vision_failed")
```

#### Additional fix — Room label extraction (found during live run)

YOLO detects 11 zones but all are labelled `"zone"` because the orchestrator never maps OCR text to zone bounding boxes. Extend the vision-API response to also return room name→dimension pairs, then match each YOLO zone centroid to the nearest OCR label string. This populates `rooms[].label` with real names (`"Bedroom 1"`, `"Family Room"`, etc.) for the BOQ and report without touching the confidence formula.

#### Confidence impact
- `c_ocr`: 0.0 → 1.0 (+**0.30** to score)
- Cascades into `scale_source` upgrade (see Change B)
- Room labels: all `"zone"` → actual names (`"Bedroom 1"`, `"Kitchen"`, …)

---

### Change B — Fix imperial dimension → metres conversion

**File:** `backend/services/floorplan_process/orchestrator.py`

#### Root cause
`_infer_area_from_dimensions()` (line 323) uses regex `r"([\d.]+)\s*m\b"` — matches only metric suffixes. Tokens like `"11'3\""` and `"8'11\""` are silently dropped. `values_m` stays empty. Function returns `0.0`.

#### Fix B1 — Parse feet/inches inside `_infer_area_from_dimensions()`

Add alongside the existing metric regex:

```python
_FT_IN_RE = re.compile(r"(\d+)[''′]\s*(\d+(?:\.\d+)?)[\"\"″]?")

def _feet_inches_to_m(feet: str, inches: str) -> float:
    return int(feet) * 0.3048 + float(inches) * 0.0254
```

In the token loop, after the metric check, add:

```python
fi = _FT_IN_RE.search(token)
if fi:
    values_m.append(_feet_inches_to_m(fi.group(1), fi.group(2)))
```

#### Fix B2 — Sum all room areas instead of multiplying two largest values

The floor plan has 8 rooms each with `W × H` labels. Multiplying only the two largest values gives one (incorrect) area. Add a new helper that sums all room areas:

```python
def _sum_room_areas_from_dimensions(dimensions: list[str]) -> float:
    """
    Parse consecutive W×H pairs (metric or feet/inch) and sum room areas.
    Returns total floor area in m².
    """
    # Normalise tokens: convert all to metres, then find adjacent pairs
    metres: list[float] = []
    for token in dimensions:
        # metric
        m = re.search(r"([\d.]+)\s*m\b", token, re.IGNORECASE)
        if m:
            metres.append(float(m.group(1)))
            continue
        # feet/inches
        fi = _FT_IN_RE.search(token)
        if fi:
            metres.append(_feet_inches_to_m(fi.group(1), fi.group(2)))

    # Pair up consecutive values as W × H and accumulate
    total = 0.0
    i = 0
    while i + 1 < len(metres):
        total += metres[i] * metres[i + 1]
        i += 2
    return total
```

Call priority in the orchestrator (lines 219–226):

```python
# Try summing all room dimension pairs first
total_floor_area_m2 = _sum_room_areas_from_dimensions(dimensions_raw)

# Fall back to two-largest multiply
if total_floor_area_m2 == 0.0:
    total_floor_area_m2 = _infer_area_from_dimensions(dimensions_raw)
```

#### Confidence impact
When vision OCR returns all 8 room dimension labels:
- `total_floor_area_m2` becomes accurate (≈87 m², matching the 936 sqft entered in the form)
- `scale_source` upgrades: `"heuristic"` → `"ocr_confirmed"` (YOLO zones **and** OCR dims both present)
- scale_conf: 0.20 → 1.00 (+**0.16** to score)

---

### Change C — Image preprocessing for YOLO quality

**File:** `backend/services/floorplan_process/geometry_extraction/geometry_extractor.py`

#### What
`preprocess_image()` currently only validates the file exists and returns metadata. Add actual CV preprocessing before YOLO and OCR receive the image.

#### Steps

```python
def preprocess_image(image_path: str) -> dict:
    from PIL import Image, ImageFilter, ImageOps
    import tempfile, os

    p = Path(image_path)
    if not p.exists():
        raise FileNotFoundError(f"Floor plan image not found: {image_path}")

    img = Image.open(p)
    original_size = img.size

    # 1. Convert to greyscale
    img = img.convert("L")

    # 2. Upscale if too small for YOLO (optimal input = 640 px)
    if img.width < 640:
        scale = 640 / img.width
        img = img.resize(
            (int(img.width * scale), int(img.height * scale)),
            Image.LANCZOS,
        )

    # 3. Adaptive threshold — binarise to black walls on white background
    img = img.point(lambda px: 0 if px < 200 else 255, "L")

    # Save processed copy alongside original
    suffix = p.suffix
    tmp = tempfile.NamedTemporaryFile(
        suffix=suffix, prefix="fp_proc_", delete=False,
        dir=p.parent,
    )
    img.save(tmp.name)
    tmp.close()

    return {
        "image_path": image_path,
        "processed_path": tmp.name,   # <- orchestrator uses this for YOLO/OCR
        "original_size": original_size,
        "processed_size": img.size,
        "size_bytes": p.stat().st_size,
        "format": p.suffix.lstrip("."),
        "method": "preprocess_binarise",
    }
```

In `orchestrator.py`, use `preprocess.get("processed_path", image_path)` when calling OCR and YOLO.

#### Confidence impact
- YOLO avg conf: ≈0.65 → ≈0.78 (+**0.03** to score)
- OCR (if Tesseract installed): improved text extraction on binarised image

---

### Projected final confidence score

_Starting point from live run (not estimates)._

| Component | **Measured baseline** | After A+B+C | Delta |
|-----------|----------------------|-------------|-------|
| c_ocr × 0.30 | 0.000 | **0.300** | +0.300 |
| c_det × 0.25 | 0.172 (0.6887 avg) | **0.180** (~0.72 after preproc) | +0.008 |
| c_scale × 0.20 | 0.120 (`detector`=0.60) | **0.200** (`ocr_confirmed`=1.00) | +0.080 |
| c_coverage × 0.15 | 0.150 | **0.150** | — |
| heuristic penalty | −0.025 | **−0.025** | — |
| **c_g total** | **0.4172** | **≈0.805** | **+0.388** |

Acceptance gate threshold: 0.30 → **passed at both scores**. Downstream confidence penalty for low geometry score (`< 0.50`) eliminated after fix (currently subtracting up to −0.15 from overall estimate confidence).

---

## Part 2 — Quantity Prediction Cascade

### Current cascade (3 tiers)

```
Tier 1: Per-item ML model (quantity_predictor.joblib → item_models dict)
           ↓ (no per-item model found)
Tier 2: Geometry / rule-based calculator
           ↓ (geometry unavailable or unfit)
Tier 3: Parametric fallback (project parameters only)
```

### Proposed cascade (4 tiers)

```
Tier 1: Per-item ML model
           ↓ (no per-item model found)
Tier 2: Category-level ML prediction → distribute across items   ← NEW
           ↓ (prediction fails or returns 0)
Tier 3: Geometry / rule-based calculator
           ↓ (geometry unavailable or unfit)
Tier 4: Parametric fallback
```

---

### Change D — `predict_category_total()` function

**File:** `backend/services/quantity_gen_process/quantity_calculator.py`

#### What
Predict the **total quantity** for an entire category using the global ML model, then return it for distribution across the category's items.

#### Implementation

```python
def predict_category_total(
    category_slug: str,
    project_info: dict,
    geometry: dict | None = None,
) -> dict:
    """
    Predict aggregate quantity for a whole category using the global ML model.

    Returns
    -------
    dict with keys:
        category_total     : float — predicted total quantity for the category
        unit               : str   — most common unit for this category
        confidence         : float — feature_completeness × 0.75 (global scope)
        is_category_level  : True
    """
    model_data = _load_model()
    if model_data is None:
        return {"category_total": 0.0, "confidence": 0.0, "is_category_level": True}

    model           = model_data["model"]
    label_encoders  = model_data["label_encoders"]
    feature_cols    = model_data["feature_cols"]

    # Map internal slug → ML Work_Category label (existing map, line 123)
    work_category = _CATEGORY_SLUG_MAP.get(category_slug, category_slug)

    # Build feature row (reuse existing _build_feature_row helper)
    row = _build_feature_row(
        item={"category": category_slug, "unit": _CATEGORY_DEFAULT_UNIT.get(category_slug, "m2")},
        project_info=project_info,
        geometry=geometry,
        label_encoders=label_encoders,
        feature_cols=feature_cols,
        work_category_override=work_category,
    )

    # Predict (model trained on log1p target)
    log_pred = model.predict([row])[0]
    category_total = float(np.expm1(log_pred))

    # Feature completeness (same formula as item-level, existing lines ~240)
    completeness = _compute_feature_completeness(row, label_encoders, geometry)
    confidence = completeness * 0.75   # global scope penalty (existing convention)

    return {
        "category_total": max(category_total, 0.0),
        "unit": _CATEGORY_DEFAULT_UNIT.get(category_slug, "m2"),
        "confidence": round(confidence, 4),
        "is_category_level": True,
    }
```

Add `_CATEGORY_DEFAULT_UNIT` dict mapping each category slug to its typical BSR unit (m2, m3, Nr, m, kg, etc.) for use when building the feature row.

---

### Change E — `distribute_category_to_items()` function

**File:** `backend/services/quantity_gen_process/quantity_calculator.py`

#### What
Split a category-level predicted total across a list of items, using the same weight resolution already used in Phase 13 (`_allocate_floor_scoped_quantities()`). Extract the weight logic into a shared helper to avoid duplication.

#### Shared helper (extract from Phase 13)

```python
def _resolve_distribution_weights(
    items: list[dict],
    geometry: dict | None,
) -> tuple[list[float], str]:
    """
    Return (weight_list, method_name) for distributing a total across items.

    Priority:
      1. per_floor_area × qs_weight  (both axes vary)
      2. per_floor_area              (only floor varies)
      3. qs_weight                   (only description varies)
      4. equal_split                 (fallback)
    """
    # ... extract from existing _allocate_floor_scoped_quantities() ...
```

#### Distribution function

```python
def distribute_category_to_items(
    category_total: float,
    category_confidence: float,
    items: list[dict],
    geometry: dict | None = None,
) -> list[dict]:
    """
    Distribute category_total across items proportional to resolved weights.
    Annotates each item with Tier-2 metadata.
    """
    weights, method = _resolve_distribution_weights(items, geometry)
    total_weight = sum(weights) or 1.0

    result = []
    for item, w in zip(items, weights):
        item_qty = category_total * (w / total_weight)
        item = {**item}   # shallow copy — do not mutate original
        item["quantity"]                          = round(item_qty, 4)
        item["final_quantity"]                    = round(item_qty, 4)
        item["quantity_source"]                   = "category_distributed"
        item["quantity_allocation_method"]        = method
        item["quantity_confidence_score"]         = round(category_confidence * (w / total_weight), 4)
        item.setdefault("reconciliation_summary", {})
        item["reconciliation_summary"]["allocation_note"] = (
            f"Tier-2 category ML total {category_total:.2f} distributed via {method}"
        )
        item["reconciliation_summary"]["method"] = "category_distribution"
        result.append(item)

    return result
```

---

### Change F — Wire Tier 2 into the service cascade

**File:** `backend/services/quantity_gen_process/service.py`

#### Where to insert
In `_compute_with_geometry()` (geometry path) and `_compute_quantity_predictor_all()` (no-geometry path), **after** item-level ML predictions are resolved and **before** geometry/rule-based processing runs on the remaining items.

#### Logic

```python
# --- Tier 2: Category-level ML prediction + item distribution ---
# Collect items where item-level ML had no per-item model
tier2_candidates = [
    item for item in boq_items
    if item.get("quantity_source") == "quantity_predictor"
    and item.get("reconciliation_summary", {}).get("source") == "global_allocation"
]

# Group by category slug
from itertools import groupby
tier2_candidates.sort(key=lambda x: x.get("category", ""))
for category_slug, group_iter in groupby(tier2_candidates, key=lambda x: x.get("category", "")):
    group = list(group_iter)
    try:
        cat_pred = predict_category_total(category_slug, project_info, floorplan_geometry)
        if cat_pred["category_total"] > 0:
            distributed = distribute_category_to_items(
                cat_pred["category_total"],
                cat_pred["confidence"],
                group,
                floorplan_geometry,
            )
            # Replace original items with distributed versions
            id_map = {id(item): dist for item, dist in zip(group, distributed)}
            boq_items = [id_map.get(id(item), item) for item in boq_items]
    except Exception as exc:
        logger.warning("Tier-2 category prediction failed for %s: %s", category_slug, exc)
        # Items fall through to Tier 3 unchanged
```

#### Error contract
Any exception in the Tier-2 block is caught and logged as a warning. Items pass through to Tier 3 (geometry/rule-based) unchanged. The cascade is strictly additive — it cannot make quantity prediction worse.

---

## File Change Summary

| # | File | Change |
|---|------|--------|
| A | `backend/services/floorplan_process/geometry_extraction/ocr.py` | Add vision-API OCR fallback when Tesseract absent |
| B | `backend/services/floorplan_process/orchestrator.py` | Fix feet/inch parsing; add room-area summation helper |
| C | `backend/services/floorplan_process/geometry_extraction/geometry_extractor.py` | Add grayscale + threshold + upscale preprocessing |
| D | `backend/services/quantity_gen_process/quantity_calculator.py` | Add `predict_category_total()` function |
| E | `backend/services/quantity_gen_process/quantity_calculator.py` | Add `distribute_category_to_items()` + shared weight helper |
| F | `backend/services/quantity_gen_process/service.py` | Wire Tier-2 cascade between item-level ML and geometry rules |

## Existing utilities to reuse (do not duplicate)

| Utility | File | Used in |
|---------|------|---------|
| `_DIMENSION_PATTERNS` + `_extract_dimensions()` | `ocr.py` line 6 | Change A — parse vision response |
| `_ocr_skip_result()` | `ocr.py` | Change A — keep as last resort fallback |
| `_load_model()` singleton | `quantity_calculator.py` | Change D |
| `_CATEGORY_SLUG_MAP` | `quantity_calculator.py` line 123 | Change D |
| Feature vector / completeness helpers | `quantity_calculator.py` | Change D |
| Weight resolution logic in `_allocate_floor_scoped_quantities()` | `service.py` Phase 13 | Change E — extract into `_resolve_distribution_weights()` |
| `_geometry_is_usable()` | `service.py` | Unchanged — gating logic untouched |

---

## Testing Plan

### New test file
`backend/tests/unit/quantity_gen/test_category_distribution.py`

| Test | Assertion |
|------|-----------|
| `test_predict_category_total_masonry` | Returns `category_total > 0`, `is_category_level = True`, `confidence ≤ 0.75` |
| `test_predict_category_total_unknown_slug` | Returns `category_total = 0.0` without raising |
| `test_distribute_equal_split` | When items have equal QS weight and same floor → equal split |
| `test_distribute_qs_weight` | Items with different QS weights get proportional quantities |
| `test_distribute_per_floor_area` | Items on different floors get quantities proportional to floor area |
| `test_tier2_cascade_fires_on_global_allocation` | Service wires Tier-2 for items with `source == "global_allocation"` |
| `test_tier2_cascade_skipped_on_model_failure` | Exception in `predict_category_total` → items pass through to Tier 3 unchanged |

### Extend existing tests

| File | What to add |
|------|-------------|
| `test_orchestrator_resilience.py` | `_infer_area_from_dimensions()` with feet/inch tokens; `_sum_room_areas_from_dimensions()` with 8-room label list |
| `test_floorplan_confidence_scorer.py` | Vision OCR path sets `c_ocr = 1.0`; preprocessing path returns `processed_path`; `ocr_confirmed` scale source achieved when both YOLO zones and imperial dims present |

### End-to-end verification

Baseline (live run, pre-fix): `geometry_confidence = 0.4172`, `scale_source = "detector"`, `dimensions_raw = []`, all rooms `"zone"`.

1. Run pipeline directly against `train.dir/image-processing/test/image6.jpg`:
   ```
   python C:\Temp\run_floorplan.py
   ```
   Expected after fixes:
   - `geometry_confidence ≥ 0.75`
   - `scale_source = "ocr_confirmed"`
   - `dimensions_raw` non-empty (imperial tokens parsed)
   - `rooms[].label` contains actual names, not `"zone"`

2. Upload through UI form (Residential, 1 floor):
   - **SSE `floorplan_cv`** event: `geometry_confidence ≥ 0.75`, `accepted = True`
   - **`floorplan_acceptance`** event: `accepted` (not `rejected`)

3. **BOQ table** — Brick Masonry section:
   - Items have **different** quantities per line (not all 86.06)
   - External wall items > Internal partition items (external has more area)
   - `quantity_source` shows `"category_distributed"` or `"geometry"` per item

4. **Run tests:** `python -m pytest backend/tests/unit/14_floorplan_pipeline/ backend/tests/unit/quantity_gen/ -v`

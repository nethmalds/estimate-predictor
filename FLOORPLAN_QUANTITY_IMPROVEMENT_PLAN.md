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
| OCR error raises exception → `_ocr_succeeded = False` | OCR module returns `_ocr_skip_result(..., "tesseract_not_found")` (no exception). Orchestrator's `_ocr_succeeded = True` because no exception propagated, but `ocr_result["ocr_skipped"]` is `True` — the success flag does NOT mean "dims found". Callers must check `ocr_result.get("ocr_skipped")` or `len(dimensions_raw) > 0`. |

---

## Already shipped (resilience scaffolding, 2026-05-20)

Commit `f8a9433` landed resilience scaffolding for the pipeline but did NOT implement any of the confidence-maximisation work below. Changes A–F are all still pending. The scaffolding affects how A–C plug in:

| Already in place | File | Reuse in this plan |
|------------------|------|--------------------|
| `_placeholder_geometry(skip_reason)` | `orchestrator.py:66` | Returned on download/PDF/preprocess failures — no change needed |
| `_ocr_skip_result(image_file, reason)` | `ocr.py:31` | Change A reuses this as the last-resort fallback when vision API also fails |
| Try/except wrappers around preprocess, OCR, YOLO | `orchestrator.py:163-204` | Change A/B/C edits land INSIDE these blocks, not around them |
| `_ocr_succeeded`, `_yolo_succeeded` flags | `orchestrator.py:174,190` | Read but do NOT reflect dimension presence; cross-check with `ocr_result["ocr_skipped"]` |
| `_log` (module logger) | `orchestrator.py:47` | Use instead of `print`/`warnings.warn` for new code paths |
| `test_orchestrator_resilience.py` (284 lines) | `tests/unit/14_floorplan_pipeline/` | Extend with NEW test classes; do not modify existing resilience classes |
| `test_yolo_degradation.py` (215 lines) | `tests/unit/14_floorplan_pipeline/` | Unchanged — YOLO degradation is a separate concern |

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
When Tesseract raises `TesseractNotFoundError` (caught at [ocr.py:63](backend/services/floorplan_process/geometry_extraction/ocr.py#L63)), instead of immediately returning `_ocr_skip_result()`, call the configured LLM API with the floor plan image and extract dimension text from the response. `_ocr_skip_result` is preserved as the last-resort fallback for when vision also fails.

#### Image input
After Change C, `image_path` passed to `extract_floorplan_text_and_dimensions` will already be the **preprocessed** (greyscale + binarised + upscaled) path. The vision API receives the same file. Open question: vision models may perform better on the ORIGINAL image (richer information) than the binarised one. Resolution: also stash `original_path` in the OCR call so Change A can call vision against the original even when Tesseract sees the processed copy. Add an `original_path` kwarg to `extract_floorplan_text_and_dimensions(image_path, original_path=None)` with default `original_path = image_path`.

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

YOLO detects 11 zones but all are labelled `"zone"` because the orchestrator never maps OCR text to zone bounding boxes.

**Vision prompt extension.** Extend the vision-API prompt to return JSON, not free text:
```json
[
  {"name": "Bedroom 1", "dimension_label": "11'3\" x 8'11\"", "bbox": [x1, y1, x2, y2]},
  ...
]
```
The `bbox` is in pixel coordinates of the image sent. Parse with `json.loads` (in a try/except — fall back to line-by-line text parsing if the model returns non-JSON).

**Centroid matching algorithm.**
```python
def _match_zones_to_labels(
    yolo_zones: list[dict],   # each has "bbox_px" and label = "zone"
    ocr_labels: list[dict],   # each has "name" and "bbox" from vision
    img_w: int, img_h: int,
) -> list[dict]:
    """Greedy nearest-centroid matching with a distance threshold.

    - Threshold = 10 % of image diagonal (calibrated for floor plans where
      labels are inside the rooms they describe).
    - Each OCR label can match at most one YOLO zone.
    - Unmatched YOLO zones keep label = "zone".
    """
    import math
    diag = math.hypot(img_w, img_h)
    threshold = diag * 0.10

    # Compute centroids once
    label_centroids = [
        ((l["bbox"][0] + l["bbox"][2]) / 2, (l["bbox"][1] + l["bbox"][3]) / 2)
        for l in ocr_labels
    ]
    used: set[int] = set()
    for zone in yolo_zones:
        x1, y1, x2, y2 = zone["bbox_px"]
        zx, zy = (x1 + x2) / 2, (y1 + y2) / 2
        best, best_dist = None, threshold
        for i, (lx, ly) in enumerate(label_centroids):
            if i in used:
                continue
            d = math.hypot(zx - lx, zy - ly)
            if d < best_dist:
                best, best_dist = i, d
        if best is not None:
            zone["label"] = ocr_labels[best]["name"]
            used.add(best)
    return yolo_zones
```

**Edge cases:**
- More YOLO zones than OCR labels (11 vs 8 in the verified case): unmatched zones retain `"zone"` — acceptable.
- OCR label far from any zone: dropped silently (above threshold).
- Two OCR labels close to the same zone: first-pass greedy wins; the other label is dropped. Document this — for floor plans, labels are inside rooms so collisions are rare.

This populates `rooms[].label` with real names (`"Bedroom 1"`, `"Kitchen"`, …) for the BOQ and report without touching the confidence formula.

#### Operational requirements (vision API)

- **Timeout:** wrap `_call_llm_vision` with a 15-second timeout. On timeout, log a warning and return `_ocr_skip_result(image_file, "vision_timeout")`.
- **Result caching:** SHA-256 the image bytes (first 24 hex chars) and cache the parsed vision response on disk at `backend/temp/vision_ocr_cache/<hash>.json`. Reuse for identical images. Same retention policy as `image_cache.py`.
- **Circuit breaker:** module-level counter of consecutive vision failures; after 5 failures within 5 minutes, short-circuit straight to `_ocr_skip_result(image_file, "vision_circuit_open")` for 60 seconds. Avoids runaway spend during upstream outages.
- **Cost note:** each uncached call costs ~$0.005–$0.05 depending on model. Cache hits are free. Document the expected per-estimate cost in the README so it's not a surprise in the bill.
- **No async required:** orchestrator stays sync. If the vision call latency becomes a UX problem, move the whole pipeline to a background task and stream via existing SSE — do not partially async the orchestrator.

#### Confidence impact
- `c_ocr`: 0.0 → 1.0 (+**0.30** to score)
- Cascades into `scale_source` upgrade (see Change B)
- Room labels: all `"zone"` → actual names (`"Bedroom 1"`, `"Kitchen"`, …)

---

### Change B — Fix imperial dimension → metres conversion

**File:** `backend/services/floorplan_process/orchestrator.py`

#### Root cause
`_infer_area_from_dimensions()` ([orchestrator.py:332](backend/services/floorplan_process/orchestrator.py#L332) — moved from line 323 by the resilience fix) uses regex `r"([\d.]+)\s*m\b"` — matches only metric suffixes. Tokens like `"11'3\""` and `"8'11\""` are silently dropped. `values_m` stays empty. Function returns `0.0`. Note: the OCR module's `_DIMENSION_PATTERNS` ([ocr.py:6-10](backend/services/floorplan_process/geometry_extraction/ocr.py#L6-L10)) DOES extract feet/inch tokens — they reach the orchestrator intact and get dropped here.

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

Call priority in the orchestrator ([orchestrator.py:220-229](backend/services/floorplan_process/orchestrator.py#L220-L229) — was lines 219–226 pre-fix):

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
`preprocess_image()` currently only validates the file exists and returns metadata. Add actual CV preprocessing before YOLO and OCR receive the image. **Original implementation used `tempfile.NamedTemporaryFile(delete=False)` next to the original — that leaks disk on every call.** Use a hash-keyed cache in the existing `_CACHE_DIR` so repeat preprocesses of the same image are O(1) cache hits.

#### Steps

```python
def preprocess_image(image_path: str) -> dict:
    import hashlib
    from PIL import Image

    p = Path(image_path)
    if not p.exists():
        raise FileNotFoundError(f"Floor plan image not found: {image_path}")

    image_bytes = p.read_bytes()
    cache_key   = hashlib.sha256(image_bytes).hexdigest()[:24]

    # Reuse the download cache directory so retention policy is shared
    from services.floorplan_process.image_cache import _CACHE_DIR
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    processed_path = _CACHE_DIR / f"{cache_key}_processed{p.suffix or '.png'}"

    img = Image.open(p)
    original_size = img.size

    if not processed_path.exists():
        # 1. Greyscale
        img = img.convert("L")

        # 2. Upscale if too small for YOLO (optimal input ≈ 640 px)
        if img.width < 640:
            scale = 640 / img.width
            img = img.resize(
                (int(img.width * scale), int(img.height * scale)),
                Image.LANCZOS,
            )

        # 3. Binarise — black walls on white background
        img = img.point(lambda px: 0 if px < 200 else 255, "L")
        img.save(processed_path)

    return {
        "image_path":     image_path,
        "processed_path": str(processed_path),
        "original_size":  original_size,
        "processed_size": img.size,
        "size_bytes":     p.stat().st_size,
        "format":         p.suffix.lstrip("."),
        "method":         "preprocess_binarise",
    }
```

#### Wire into orchestrator call sites

The orchestrator's resilience fallback (when `preprocess_image` raises, at [orchestrator.py:165-171](backend/services/floorplan_process/orchestrator.py#L165-L171)) currently produces a dict WITHOUT `processed_path`. Update the fallback so both paths produce the same shape:

```python
except Exception as exc:
    warnings.warn(...)
    preprocess = {
        "image_path":     image_path,
        "processed_path": image_path,   # <- NEW — falls back to original
        "size_bytes":     0,
        "format":         "unknown",
        "method":         "failed",
    }
```

Then call OCR ([orchestrator.py:176](backend/services/floorplan_process/orchestrator.py#L176)) and YOLO ([orchestrator.py:192-194](backend/services/floorplan_process/orchestrator.py#L192-L194)) with `preprocess["processed_path"]`. Vision API fallback in Change A also receives the same path (or the original — see Change A "Image input" note).

#### Cache invalidation
Same SHA-256 image bytes → same `processed_path`. Different bytes → different key. No deletion path needed — the cache directory shares retention with `image_cache.py`. If retention isn't implemented yet, add a TODO; do not block this change on it.

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
| `_DIMENSION_PATTERNS` + `_extract_dimensions()` | `ocr.py:6,24` | Change A — parse vision response |
| `_ocr_skip_result()` | `ocr.py:31` (added by f8a9433) | Change A — last-resort fallback when vision also fails |
| `_placeholder_geometry()` | `orchestrator.py:66` (added by f8a9433) | Reused by download/PDF resilience — Changes A–C do not touch it |
| `_log` (module logger) | `orchestrator.py:47` (added by f8a9433) | Use for new code paths instead of `print`/`warnings.warn` |
| `_CACHE_DIR` | `image_cache.py:19` | Change C — share preprocessing cache with download cache |
| `download_and_cache()` | `image_cache.py:44` | Unchanged — URL resolution path |
| `_load_model()` singleton | `quantity_calculator.py` | Change D |
| `_CATEGORY_SLUG_MAP` | `quantity_calculator.py` line 123 | Change D |
| Feature vector / completeness helpers (`_compute_feature_completeness`) | `quantity_calculator.py:381,417` | Change D |
| Weight resolution logic in `_allocate_floor_scoped_quantities()` | `service.py:606` Phase 13 | Change E — extract into `_resolve_distribution_weights()` |
| `_geometry_is_usable()` | `service.py` | Unchanged — gating logic untouched |

---

## Testing Plan

### New test files

| File | Tests | Assertion |
|------|-------|-----------|
| `backend/tests/unit/08_quantity_estimation/test_category_distribution.py`<br>_(numbered folders per repo convention — NOT `quantity_gen/`)_ | `test_predict_category_total_masonry` | Returns `category_total > 0`, `is_category_level = True`, `confidence ≤ 0.75` |
| | `test_predict_category_total_unknown_slug` | Returns `category_total = 0.0` without raising |
| | `test_distribute_equal_split` | When items have equal QS weight and same floor → equal split |
| | `test_distribute_qs_weight` | Items with different QS weights get proportional quantities |
| | `test_distribute_per_floor_area` | Items on different floors get quantities proportional to floor area |
| | `test_tier2_cascade_fires_on_global_allocation` | Service wires Tier-2 for items with `source == "global_allocation"` |
| | `test_tier2_cascade_skipped_on_model_failure` | Exception in `predict_category_total` → items pass through to Tier 3 unchanged |
| `backend/tests/unit/14_floorplan_pipeline/test_vision_ocr_fallback.py` | `test_vision_called_when_tesseract_missing` | Patch `pytesseract.image_to_string` to raise `TesseractNotFoundError`; assert `_call_llm_vision` is invoked and dimensions populated |
| | `test_vision_response_cached` | Same image bytes → second call hits disk cache, never calls LLM |
| | `test_vision_timeout_falls_back_to_skip_result` | LLM client times out → returns `_ocr_skip_result(..., "vision_timeout")` |
| | `test_circuit_breaker_opens_after_5_failures` | After 5 consecutive failures, vision call is short-circuited for 60s |
| | `test_vision_json_response_parsed` | Mock LLM returns valid JSON room list → dimensions and labels both extracted |
| | `test_vision_non_json_response_falls_back_to_text_parse` | Mock LLM returns plain text → dimensions still extracted via existing `_DIMENSION_PATTERNS` |
| | **CRITICAL:** all tests must mock `_call_llm_vision` — NEVER hit the real API in CI |
| `backend/tests/unit/14_floorplan_pipeline/test_preprocess_cache.py` | `test_processed_path_deterministic` | Same image bytes → same `processed_path` across calls |
| | `test_cache_hit_skips_pil_work` | Patch `PIL.Image.point`; verify it's NOT called when cached file exists |
| | `test_fallback_returns_image_path_when_preprocess_fails` | Orchestrator's exception path: fallback dict's `processed_path == image_path` |
| `backend/tests/unit/14_floorplan_pipeline/test_room_label_matching.py` | `test_centroid_matching_within_threshold` | 8 OCR labels, 11 YOLO zones → labels matched by proximity, extras stay `"zone"` |
| | `test_no_match_when_label_far_from_zone` | Label centroid > 10% diagonal away → no match, zone stays `"zone"` |
| | `test_one_label_per_zone` | Two labels close to same zone → first wins (greedy) |

### Extend existing tests (add new classes — do NOT modify existing ones)

| File | Existing state | What to ADD |
|------|----------------|-------------|
| `test_orchestrator_resilience.py` | 284 lines, shipped in f8a9433. Existing classes cover YOLO failure, OCR failure, both-fail. **Do not modify these.** | New class `TestImperialDimensionParsing`: `_infer_area_from_dimensions()` with feet/inch tokens, mixed metric/imperial, malformed input. New class `TestRoomAreaSummation`: `_sum_room_areas_from_dimensions()` with 8-room label list, odd-count tokens, all-metric, all-imperial. |
| `test_floorplan_confidence_scorer.py` | Existing scorer tests for `compute_geometry_confidence`. | Vision OCR path sets `c_ocr = 1.0`; preprocessing path returns `processed_path`; `ocr_confirmed` scale source achieved when both YOLO zones and imperial dims present. |

### End-to-end verification

Baseline (live run, pre-fix): `geometry_confidence = 0.4172`, `scale_source = "detector"`, `dimensions_raw = []`, all rooms `"zone"`. The post-fix resilience scaffolding does NOT change this baseline — confidence work is still pending.

> **Note:** the verification image `train.dir/image-processing/test/image6.jpg` and runner script `C:\Temp\run_floorplan.py` live on the author's local machine, not in the repo. For a portable reproducer, commit a representative floor plan to `backend/tests/fixtures/floorplans/` and a `scripts/verify_floorplan.py` runner.

1. Run pipeline directly against the verification image (local) or `backend/tests/fixtures/floorplans/sample.jpg` (CI):
   ```
   python scripts/verify_floorplan.py <image_path>
   ```
   Expected after fixes:
   - `geometry_confidence ≥ 0.75`
   - `scale_source = "ocr_confirmed"`
   - `dimensions_raw` non-empty (imperial tokens parsed)
   - `rooms[].label` contains actual names, not `"zone"`
   - `_ocr_succeeded = True` AND `ocr_result["ocr_skipped"]` absent or `False`

2. Upload through UI form (Residential, 1 floor):
   - **SSE `floorplan_cv`** event: `geometry_confidence ≥ 0.75`, `accepted = True`
   - **`floorplan_acceptance`** event: `accepted` (not `rejected`)

3. **BOQ table** — Brick Masonry section:
   - Items have **different** quantities per line (not all 86.06)
   - External wall items > Internal partition items (external has more area)
   - `quantity_source` shows `"category_distributed"` or `"geometry"` per item

4. **Run tests:** `python -m pytest backend/tests/unit/14_floorplan_pipeline/ backend/tests/unit/08_quantity_estimation/ -v`

---

## Operational concerns (added 2026-05-20 review)

### Vision API budget
Each uncached call costs ~$0.005–$0.05 depending on model. With caching (SHA-256 of image bytes), repeated uploads of the same plan are free. Cost ceiling per estimate: 1 vision call. Document in the README before shipping.

### Latency
Vision API adds ~2–10s p50 to the pipeline. The orchestrator stays sync; the existing SSE stream (`floorplan_cv` event) already handles the long-running case. Acceptance criteria: p95 pipeline latency under 15s including vision call. If it exceeds, move the whole pipeline to a background task — do not partially async the orchestrator.

### Disk usage
Change C adds preprocessed copies (~2× original size due to upscale) + Change A adds vision response cache (~2KB JSON per image). Both live under `backend/temp/floorplans/` and `backend/temp/vision_ocr_cache/`. Expected growth: ~250KB per unique floor plan. Document retention policy (e.g. 30-day TTL via a `cron`/scheduled cleanup task) before shipping.

### Tracked cache file regression (out of plan scope)
Commit `f8a9433` accidentally committed three cache JPGs to `backend/temp/floorplans/`. These should never be in git. Track via a separate cleanup PR that adds `backend/temp/` to `.gitignore` and `git rm --cached`s the three files. Not blocking for this plan.

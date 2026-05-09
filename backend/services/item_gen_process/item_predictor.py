"""Real Item Predictor — Random Forest multi-label BOQ item predictor.

Loads ``infrastructure/ai/models/item_pred/item_predictor.joblib`` once (lazy
singleton) and maps ``project_info`` fields into the 6-column encoded feature
vector that the trained MultiOutputClassifier expects.

Artifact schema
---------------
The joblib file is a dict with keys:
  - ``model``           : sklearn MultiOutputClassifier (Random Forest)
  - ``mlb``             : sklearn MultiLabelBinarizer  (work-category labels)
  - ``label_encoders``  : dict[str, LabelEncoder] — keys: Project_Type, Roof_Type, Ceiling_Type
  - ``feature_cols``    : ['Total_Area', 'Floors', 'Budget_enc',
                           'Project_Type_enc', 'Roof_Type_enc', 'Ceiling_Type_enc']
  - ``budget_order``    : ordered list of budget category strings
  - ``best_model_name`` : str (informational)
  - ``work_categories`` : list[str] (informational)
  - ``cat_to_items``    : dict[category, list[item_descriptions]]
  - ``metrics``         : dict (informational)

Public API
----------
predict_boq_items(project_info: dict) -> list[str]
    Returns a deduplicated list of BSR work-item description strings predicted
    for the project.
"""
from __future__ import annotations

import math
import re
from pathlib import Path
from typing import Any



# ---------------------------------------------------------------------------
# Model artifact path
# ---------------------------------------------------------------------------
_MODEL_PATH = (
    Path(__file__).resolve().parents[2]
    / "infrastructure" / "ai" / "models" / "item_pred" / "item_predictor.joblib"
)

# Lazy-loaded singleton components
_artifact: dict | None = None


def _load_model() -> None:
    """Load the joblib artifact into module-level singleton (once)."""
    global _artifact  # noqa: PLW0603
    if _artifact is not None:
        return
    try:
        import joblib  # type: ignore[import]
    except ImportError as exc:
        raise ImportError(
            "joblib is required for Item Predictor. Install with: pip install joblib"
        ) from exc

    _artifact = joblib.load(str(_MODEL_PATH))
    mlb = _artifact["mlb"]


# ---------------------------------------------------------------------------
# Public function
# ---------------------------------------------------------------------------

def predict_boq_items(project_info: dict) -> list[str]:
    """Predict BOQ work items from *project_info* using the real Item Predictor.

    Returns a deduplicated list of BSR item description strings.
    """
    return [entry["description"] for entry in predict_boq_items_with_confidence(project_info)]


def predict_boq_items_with_confidence(project_info: dict) -> list[dict]:
    """Predict BOQ work items and preserve per-item confidence scores.

    Returns
    -------
    list[dict]
        Each entry: ``{"description": str, "source_confidence": float,
        "predicted_category": str}``
        sorted by descending confidence.
    """
    _load_model()

    import numpy as np  # type: ignore[import]

    art = _artifact  # type: ignore[index]
    model = art["model"]
    mlb = art["mlb"]
    label_encoders: dict = art["label_encoders"]
    budget_order: list[str] = art.get("budget_order", [
        "standard", "semi-luxury", "luxury"
    ])
    cat_to_items: dict = art.get("cat_to_items", {})

    # -----------------------------------------------------------------------
    # Build the encoded feature row
    # -----------------------------------------------------------------------
    parameters: dict = project_info.get("parameters") or {}

    total_area_m2 = _parse_area_to_m2(parameters.get("built_up_area"))
    floors = max(int(project_info.get("floors") or 1), 1)
    budget_cat = _normalise_budget_category(parameters.get("finish_level"))
    project_type = _normalise_project_type(project_info.get("building_type"))
    roof_type = _normalise_roof_type(parameters.get("roof_type"))
    ceiling_type = _normalise_ceiling_type(parameters.get("ceiling_type"))

    # Budget ordinal encoding (position in budget_order list)
    budget_enc = _encode_ordinal(budget_cat, budget_order)

    # Label-encode categorical features (unknown → 0 via safe fallback)
    project_type_enc = _safe_le_transform(
        label_encoders.get("Project_Type"), project_type
    )
    roof_type_enc = _safe_le_transform(
        label_encoders.get("Roof_Type"), roof_type
    )
    ceiling_type_enc = _safe_le_transform(
        label_encoders.get("Ceiling_Type"), ceiling_type
    )

    # feature_cols: ['Total_Area', 'Floors', 'Budget_enc',
    #                'Project_Type_enc', 'Roof_Type_enc', 'Ceiling_Type_enc']
    X = np.array([[
        total_area_m2,
        floors,
        budget_enc,
        project_type_enc,
        roof_type_enc,
        ceiling_type_enc,
    ]], dtype=float)

    # -----------------------------------------------------------------------
    # Multi-label prediction → work category names (with confidence sorting)
    # -----------------------------------------------------------------------
    y_pred = model.predict(X)          # shape (1, n_labels) — binary array

    # Per-estimator probabilities for confidence-based sorting
    try:
        y_proba = model.predict_proba(X)  # list of (1,2) arrays
        probs: dict[str, float] = {
            cat: float(proba[0][1])
            for cat, proba in zip(mlb.classes_, y_proba)
        }
    except Exception:
        probs = {
            cat: float(v)
            for cat, v in zip(mlb.classes_, y_pred[0])
        }

    # Collect predicted categories sorted by confidence (highest first)
    raw_cats: list[str] = [
        cat for cat, pred in zip(mlb.classes_, y_pred[0]) if pred == 1
    ]
    predicted_categories: list[str] = sorted(
        raw_cats, key=lambda c: probs.get(c, 0.0), reverse=True
    )


    # -----------------------------------------------------------------------
    # Expand categories → item descriptions via cat_to_items (up to 10 each)
    # Preserve per-item confidence from the category probability.
    # -----------------------------------------------------------------------
    item_to_cat_conf: dict[str, tuple[str, float]] = {}  # desc → (category, conf)
    for cat in predicted_categories:
        cat_conf = probs.get(cat, 0.0)
        cat_items = cat_to_items.get(cat, [])
        for item_desc in cat_items[:10]:
            if item_desc not in item_to_cat_conf:
                item_to_cat_conf[item_desc] = (cat, cat_conf)

    # If cat_to_items is empty fall back to returning category names directly
    if not item_to_cat_conf and predicted_categories:
        for cat in predicted_categories:
            item_to_cat_conf[cat.lower()] = (cat, probs.get(cat, 0.0))

    # -----------------------------------------------------------------------
    # Post-prediction business rules
    # -----------------------------------------------------------------------
    plain_items = _apply_rules(project_info, set(item_to_cat_conf.keys()))

    result: list[dict] = sorted(
        [
            {
                "description":       desc,
                "source_confidence": round(item_to_cat_conf.get(desc, ("", 0.0))[1], 4),
                "predicted_category": item_to_cat_conf.get(desc, (desc, 0.0))[0],
            }
            for desc in plain_items
        ],
        key=lambda d: d["source_confidence"],
        reverse=True,
    )
    return result


# ---------------------------------------------------------------------------
# Feature normalisation helpers
# ---------------------------------------------------------------------------

_BUDGET_MAP: dict[str, str] = {
    # MVED canonical values
    "basic":     "standard",
    "high_end":  "luxury",
    # Legacy / free-text values
    "extra low budget": "standard",
    "low budget": "standard",
    "normal": "standard",
    "standard": "standard",
    "standard / budget": "standard",
    "budget": "standard",
    "semi-luxury": "semi-luxury",
    "semi luxury": "semi-luxury",
    "semi": "semi-luxury",
    "luxury": "luxury",
    "full luxury": "luxury",
    "full": "luxury",
    "high": "luxury",
    "high budget": "luxury",
}

# Label encoder classes (lowercase) as stored in the artifact:
#   Roof_Type    : ['asbestos sheet', 'clay tile', 'rc flat slab', 'unknown']
#   Ceiling_Type : ['asbestos flat', 'gypsum/mineral fibre', 'lunumidella timber', 'unknown']
_ROOF_TYPE_MAP: dict[str, str] = {
    # MVED canonical values
    "flat_slab":    "rc flat slab",
    "pitched":      "clay tile",
    "half_pitched": "clay tile",
    "metal_sheet":  "unknown",
    # Legacy / free-text values
    "clay tile": "clay tile",
    "clay": "clay tile",
    "tile": "clay tile",
    "asbestos": "asbestos sheet",
    "asbestos sheet": "asbestos sheet",
    "rc flat slab": "rc flat slab",
    "flat": "rc flat slab",
    "slab": "rc flat slab",
    "concrete slab": "rc flat slab",
    "flat concrete slab": "rc flat slab",
    "flat slab": "rc flat slab",
}

# Ceiling label encoder classes in the artifact
# Map common user inputs → one of the four known classes
_CEILING_TYPE_MAP: dict[str, str] = {
    # MVED canonical values
    "board":    "gypsum/mineral fibre",   # generic board → closest class
    # Legacy / free-text values
    "gypsum": "gypsum/mineral fibre",
    "gypsum board": "gypsum/mineral fibre",
    "gypsum/mineral fibre": "gypsum/mineral fibre",
    "mineral fibre": "gypsum/mineral fibre",
    "pvc": "gypsum/mineral fibre",
    "asbestos": "asbestos flat",
    "asbestos flat": "asbestos flat",
    "asbestos sheet": "asbestos flat",
    "timber": "lunumidella timber",
    "lunumidella timber": "lunumidella timber",
    "lunumidella": "lunumidella timber",
    "wood": "lunumidella timber",
    "concrete": "unknown",
    "none": "unknown",
    "unknown": "unknown",
    "": "unknown",
}

# Project Type label encoder classes (title-case as stored in artifact):
#   ['Apartment Building', 'Auditorium …', 'Commercial Building',
#    'Educational Building', 'Government Building …', 'Healthcare Building',
#    'Luxury Residential House', 'Renovation/Repair', 'Residential House']
_PROJECT_TYPE_MAP: dict[str, str] = {
    "residential house": "Residential House",
    "residential": "Residential House",
    "house": "Residential House",
    "luxury residential": "Luxury Residential House",
    "luxury house": "Luxury Residential House",
    "apartment": "Apartment Building",
    "apartment building": "Apartment Building",
    "flat": "Apartment Building",
    "commercial": "Commercial Building",
    "commercial building": "Commercial Building",
    "office": "Commercial Building",
    "shop": "Commercial Building",
    "educational": "Educational Building",
    "school": "Educational Building",
    "university": "Educational Building",
    "healthcare": "Healthcare Building",
    "hospital": "Healthcare Building",
    "government": "Government Building  New",
    "industrial": "Commercial Building",
    "warehouse": "Commercial Building",
    "renovation": "Renovation/Repair",
    "repair": "Renovation/Repair",
}


def _normalise_budget_category(value: str | None) -> str:
    raw = str(value or "").strip().lower()
    return _BUDGET_MAP.get(raw, "standard")


def _normalise_project_type(value: str | None) -> str:
    raw = str(value or "").strip().lower()
    return _PROJECT_TYPE_MAP.get(raw, "Residential House")


def _normalise_roof_type(value: str | None) -> str:
    """Return a lowercase roof type matching the label encoder classes."""
    raw = str(value or "").strip().lower()
    if "clay" in raw and "tile" in raw:
        return "clay tile"
    if "asbestos" in raw:
        return "asbestos sheet"
    if "rc" in raw or "r.c" in raw or "slab" in raw or "flat" in raw:
        return "rc flat slab"
    return _ROOF_TYPE_MAP.get(raw, "unknown")


def _normalise_ceiling_type(value: str | None) -> str:
    """Return a ceiling type string matching the label encoder classes:
    'asbestos flat' | 'gypsum/mineral fibre' | 'lunumidella timber' | 'unknown'
    """
    raw = str(value or "").strip().lower()
    # Direct lookup first
    if raw in _CEILING_TYPE_MAP:
        return _CEILING_TYPE_MAP[raw]
    # Fuzzy keyword matching
    if "gypsum" in raw or "mineral" in raw or "pvc" in raw:
        return "gypsum/mineral fibre"
    if "asbestos" in raw:
        return "asbestos flat"
    if "timber" in raw or "wood" in raw or "lunumidella" in raw:
        return "lunumidella timber"
    return "unknown"


def _parse_area_to_m2(value: str | float | None, default_m2: float = 167.2) -> float:
    """Return the built_up_area in m² (the unit the item predictor was trained on).

    Default 167.2 m² ≈ 1,800 sq ft.
    """
    if value is None:
        return default_m2
    raw = str(value).strip().lower()
    number_match = re.search(r"[\d.]+", raw)
    if not number_match:
        return default_m2
    num = float(number_match.group())
    # Explicitly m²
    if "m2" in raw or "m²" in raw or "sqm" in raw or "sq m" in raw:
        return round(num, 2)
    # Explicitly sq ft → convert to m²
    if "sq ft" in raw or "sqft" in raw or "ft" in raw:
        return round(num * 0.092903, 2)
    # Heuristic: values above 300 are almost certainly sq ft
    if num > 300:
        return round(num * 0.092903, 2)
    return round(num, 2)  # assume m²


def _encode_ordinal(value: str, order: list[str]) -> int:
    """Encode a value as its 0-based position in *order*; default to 0."""
    try:
        return order.index(value)
    except ValueError:
        return 0


def _safe_le_transform(le: Any, value: str) -> int:
    """Transform *value* with a LabelEncoder; return 0 on unseen labels."""
    if le is None:
        return 0
    try:
        return int(le.transform([value])[0])
    except Exception:
        # Unseen label — try to find the closest known class
        classes: list[str] = list(le.classes_)
        lower_val = value.lower()
        for cls in classes:
            if lower_val in cls.lower() or cls.lower() in lower_val:
                try:
                    return int(le.transform([cls])[0])
                except Exception:
                    pass
        return 0


# ---------------------------------------------------------------------------
# Business rules (applied after threshold)
# ---------------------------------------------------------------------------

def _apply_rules(project_info: dict, items: set[str]) -> set[str]:
    parameters: dict = project_info.get("parameters") or {}
    building_type = str(project_info.get("building_type") or "").lower()
    floors = int(project_info.get("floors") or 1)
    roof_raw = str(parameters.get("roof_type") or "").strip().lower()

    # Universal rules
    if floors > 1:
        items.add("staircase work")

    if "flat" in roof_raw or "slab" in roof_raw or "rc" in roof_raw:
        items.add("waterproofing work")

    # ── Commercial rules ──────────────────────────────────────────────────────
    if building_type == "commercial":
        primary_use = str(parameters.get("primary_use_type") or "").strip().lower()
        washroom_count = int(parameters.get("washroom_count") or 1)

        items.add("commercial toilet / washroom fit-out")

        if primary_use in ("restaurant", "food & beverage", "kitchen"):
            items.add("commercial kitchen exhaust and ventilation")
            items.add("grease trap and drainage")

        if primary_use in ("hotel", "serviced apartment"):
            items.add("elevator / lift installation")

        if washroom_count >= 4:
            items.add("centralised plumbing riser and distribution")

    # ── Industrial rules ──────────────────────────────────────────────────────
    if building_type == "industrial":
        heavy_machinery = str(parameters.get("heavy_machinery_load") or "").strip().lower()
        hazardous = str(parameters.get("hazardous_materials") or "").strip().lower()
        ventilation = str(parameters.get("specialized_ventilation") or "").strip().lower()
        facility = str(parameters.get("facility_type") or "").strip().lower()

        if heavy_machinery == "yes":
            items.add("heavy-duty industrial floor slab")
            items.add("reinforced foundation for machinery")

        if hazardous == "yes":
            items.add("chemical-resistant floor coating")
            items.add("fire suppression system")
            items.add("hazardous material containment bund")

        if ventilation == "yes":
            items.add("industrial fume extraction system")
            items.add("dust collection and filtration unit")

        if "cold storage" in facility:
            items.add("cold room insulated panel system")
            items.add("refrigeration plant room")

    return items

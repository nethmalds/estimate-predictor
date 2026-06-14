"""Quantity Predictor — quantity prediction.

Loads ``infrastructure/ai/models/quantity_pred/quantity_predictor.joblib``.

Artifact schema (saved_model_v2 format)
----------------------------------------
The joblib file is a dict with keys:
  - ``model``          : global sklearn estimator (fitted on log1p-transformed target)
  - ``label_encoders`` : dict[col_name, LabelEncoder] — one encoder per categorical column
  - ``item_models``    : dict[work_item_str, fitted_model] — per-item models
  - ``feature_cols``   : list[str] — ordered list of ALL feature column names
  - ``num_cols``       : list[str] — numeric feature names (subset of feature_cols)
  - ``cat_cols``       : list[str] — categorical feature names (subset of feature_cols)

Feature schema expected by the model
--------------------------------------
Numeric (num_cols):
  area_imputed, log_area, area_per_floor, log_area_floor,
  No. of Floors, Year, is_renovation

Categorical (cat_cols):
  Project_Type, Budget_Category, Location, Soil_Type,
  Roof_Type, Ceiling_Type, Work_Category, Unit, Material_Type

Target encoding:
  Model was trained on log1p(quantity). Predictions are inverted with np.expm1().

Public API
----------
predict_quantity(item: dict, project_info: dict) -> dict
    Returns a QuantityPrediction dict with keys:
      quantity, method, is_item_level, model_scope,
      prediction_confidence, feature_completeness,
      unknown_feature_count, unknown_feature_names, allocation_mode.
"""
from __future__ import annotations

import math
import re
from datetime import datetime
from pathlib import Path
from typing import Any



_MODEL_PATH = (
    Path(__file__).resolve().parents[2]
    / "infrastructure" / "ai" / "models" / "quantity_pred" / "quantity_predictor.joblib"
)

_artifact: dict | None = None
_quantity_predictor_checked: bool = False


def _try_load_quantity_predictor() -> None:
    """Attempt to load the Quantity Predictor joblib artifact (once per process)."""
    global _artifact, _quantity_predictor_checked  # noqa: PLW0603
    if _quantity_predictor_checked:
        return
    _quantity_predictor_checked = True
    if not _MODEL_PATH.exists():
        return
    try:
        import joblib  # type: ignore[import]
        _artifact = joblib.load(str(_MODEL_PATH))
    except Exception:
        _artifact = None


def predict_quantity(
    item: dict[str, Any],
    project_info: dict[str, Any],
) -> dict[str, Any]:
    """Predict the quantity for a single BOQ item.

    Uses the real Quantity Predictor if available.

    Returns
    -------
    dict
        ``QuantityPrediction`` with keys:
          - ``quantity``             : float (≥ 0)
          - ``method``               : str  ("quantity_predictor")
          - ``is_item_level``        : bool
          - ``model_scope``          : "item_level" | "global"
          - ``prediction_confidence``: float 0–1
          - ``feature_completeness`` : float 0–1  (1 − (u+d)/n)
          - ``unknown_feature_count``: int
          - ``unknown_feature_names``: list[str]
          - ``allocation_mode``      : "direct" | "global_allocation"
    """
    _try_load_quantity_predictor()

    if _artifact is not None:
        return _predict_with_quantity_predictor(item, project_info)

    return {
        "quantity":              0.0,
        "method":                "quantity_predictor",
        "is_item_level":         False,
        "model_scope":           "none",
        "prediction_confidence": 0.0,
        "feature_completeness":  0.0,
        "unknown_feature_count": 0,
        "unknown_feature_names": [],
        "allocation_mode":       "direct",
    }


# ---------------------------------------------------------------------------
# Category slug → ML Work_Category label
# ---------------------------------------------------------------------------
# The ML model was trained on specific Work_Category strings. BOQ items carry
# internal short slugs (e.g. "finishes", "roof"). We must map them before
# passing features to the model, otherwise it sees an unknown label → ~zero qty.
# Work_Category values MUST match the label encoder training classes exactly:
# ['Brick Masonry', 'Concrete Works', 'Demolition & Removal', 'Doors, Windows & Glazing',
#  'Electrical & Mechanical', 'Excavation & Earthwork', 'External & Civil Works',
#  'Flooring & Tiling', 'Formwork', 'Miscellaneous', 'Other', 'Painting & Finishes',
#  'Piling & Substructure', 'Plastering & Rendering', 'Preliminary & General',
#  'Reinforcement', 'Roofing & Ceiling', 'Sanitary & Plumbing',
#  'Testing & Commissioning']
_SLUG_TO_WORK_CATEGORY: dict[str, str] = {
    "structure":      "Concrete Works",
    "foundation":     "Piling & Substructure",
    "masonry":        "Brick Masonry",
    "finishes":       "Plastering & Rendering",
    "roof":           "Roofing & Ceiling",
    "openings":       "Doors, Windows & Glazing",
    "electrical":     "Electrical & Mechanical",
    "plumbing":       "Sanitary & Plumbing",
    "site":           "Excavation & Earthwork",
    "external":       "External & Civil Works",
    "demolitions":    "Demolition & Removal",
    "preliminaries":  "Preliminary & General",
    "misc":           "Miscellaneous",
}

# Category slug → sensible default unit for the ML model
_SLUG_TO_DEFAULT_UNIT: dict[str, str] = {
    "structure":      "m³",
    "foundation":     "m³",
    "masonry":        "m³",
    "finishes":       "m²",
    "roof":           "m²",
    "openings":       "m²",
    "electrical":     "Nr",
    "plumbing":       "Nr",
    "site":           "m³",
    "external":       "m³",
    "demolitions":    "m²",
    "preliminaries":  "m³",
    "misc":           "m³",
}

# Category slug → Material_Type for the ML model
# Values MUST match the label encoder training classes exactly:
# ['Aluminium/Glass', 'Ceiling/Roofing Sheet', 'Concrete', 'Earthwork/Aggregate',
#  'Electrical', 'General', 'Landscaping', 'Masonry', 'PVC/Plastic', 'Paint/Chemical',
#  'Paving', 'Sanitary Ware', 'Steel/Metal', 'Tiles', 'Timber']
_SLUG_TO_MATERIAL_TYPE: dict[str, str] = {
    "structure":      "Concrete",
    "foundation":     "Concrete",
    "masonry":        "Masonry",
    "finishes":       "Masonry",
    "roof":           "Timber",
    "openings":       "Aluminium/Glass",
    "electrical":     "Electrical",
    "plumbing":       "Sanitary Ware",
    "site":           "Earthwork/Aggregate",
    "external":       "Earthwork/Aggregate",
    "demolitions":    "General",
    "preliminaries":  "General",
    "misc":           "General",
}

# Flooring/tiling items within "finishes" carry Material_Type="Tiles" and
# Work_Category="Flooring & Tiling". Detected via description + unit.
_FLOORING_KEYWORDS = {"floor", "tile", "tiling", "terrazzo", "vinyl", "granolithic", "screed"}
_PAINTING_KEYWORDS = {"paint", "emulsion", "primer", "enamel", "weathershield"}

# Numeric defaults used when a field is missing from the row.
# Year is pinned to the model's training year (2025) to avoid drift.
_TRAINING_YEAR: int = 2025
_NUM_DEFAULTS: dict[str, float] = {
    "area_imputed":    200.0,
    "log_area":        math.log1p(200.0),
    "area_per_floor":  100.0,
    "log_area_floor":  math.log1p(100.0),
    "No. of Floors":   2.0,
    "Year":            float(_TRAINING_YEAR),
    "is_renovation":   0.0,
}


# Unit normalisation map — maps common aliases to the exact bytes stored in the
# label encoder (verified against the joblib artifact).
_UNIT_NORMALISE: dict[str, str] = {
    # m² variants
    "m2":   "m\u00b2",
    "m²":   "m\u00b2",
    "sqm":  "m\u00b2",
    "sq m": "m\u00b2",
    "m 2":  "m\u00b2",
    # m³ variants
    "m3":   "m\u00b3",
    "m³":   "m\u00b3",
    "cum":  "m\u00b3",
    "m 3":  "m\u00b3",
    # linear
    "lm":   "m",
    "l.ft": "m",
    "lft":  "m",
    "lf":   "m",
    # count
    "no":   "Nr",
    "no.": "Nr",
    "nr.":  "Nr",
    "nr":   "Nr",
    "nos":  "Nr",
    "each": "Nr",
    # weight
    "kg":   "Kg",
    "kgs":  "Kg",
    # mass / percentage
    "t":    "Kg",
}


def _normalise_unit(raw: str) -> str:
    """Map unit strings to exact LabelEncoder training values."""
    stripped = raw.strip()
    key = stripped.lower()
    if key in _UNIT_NORMALISE:
        return _UNIT_NORMALISE[key]
    # Handle 'Nr.' or 'Nr' with trailing punctuation
    if key.startswith("nr"):
        return "Nr"
    return stripped  # return as-is; will be encoded as 0 if unknown


def _build_feature_array(row: dict[str, Any]) -> "tuple[Any, list[str]]":
    """Build the numpy feature vector expected by the model.

    Returns
    -------
    (X, unknown_names)
        * ``X``             — numpy array of shape (1, n_features)
        * ``unknown_names`` — list of categorical column names whose value was unknown
    """
    import numpy as np  # type: ignore[import]

    art = _artifact  # type: ignore[index]
    num_cols: list[str] = art["num_cols"]
    cat_cols: list[str] = art["cat_cols"]
    encoders: dict = art["label_encoders"]

    feats: list[float] = []
    unknown_names: list[str] = []

    # Numeric features
    for col in num_cols:
        feats.append(float(row.get(col, _NUM_DEFAULTS.get(col, 0.0))))

    # Categorical features — LabelEncoder integer encoding
    for col in cat_cols:
        le = encoders[col]
        val = str(row.get(col, "Unknown")).strip()
        if val in list(le.classes_):
            feats.append(float(le.transform([val])[0]))
        else:
            feats.append(0.0)
            unknown_names.append(col)

    return np.array(feats, dtype=float).reshape(1, -1), unknown_names


def _predict_with_quantity_predictor(
    item: dict[str, Any],
    project_info: dict[str, Any],
) -> dict[str, Any]:
    """Run inference against the loaded quantity_predictor artifact.

    Strategy:
      1. Build feature row from item + project_info.
      2. If the item description matches a per-item model key, use that model.
      3. Otherwise use the global model.
      4. Inverse-transform via np.expm1() (model trained on log1p target).
      5. Compute feature_completeness = 1 − (u + d) / max(n, 1).
    """
    try:
        import numpy as np  # type: ignore[import]

        art = _artifact  # type: ignore[index]
        parameters = project_info.get("parameters") or {}

        # ----------------------------------------------------------------
        # Derived numeric features
        # ----------------------------------------------------------------
        area_m2 = _parse_area_to_m2(parameters.get("built_up_area"))
        floors = max(int(project_info.get("floors") or 1), 1)
        area_per_floor = area_m2 / floors if floors > 0 else area_m2

        log_area = math.log1p(area_m2)
        log_area_floor = math.log1p(area_per_floor)

        year = _TRAINING_YEAR
        is_renovation = 0

        description: str = item.get("description") or item.get("Work_Item") or ""
        description_key: str = description.strip().lower()

        raw_category: str = (item.get("category") or "misc").lower()
        work_category: str = _SLUG_TO_WORK_CATEGORY.get(raw_category, "Concrete Works")
        if item.get("work_category"):
            work_category = str(item["work_category"]).strip()

        raw_unit: str = (item.get("unit") or "").strip()
        unit: str = _normalise_unit(raw_unit) if raw_unit else _SLUG_TO_DEFAULT_UNIT.get(raw_category, "m\u00b3")

        desc_lower = description.lower()

        raw_material: str = (item.get("material_type") or "").strip()
        if raw_material:
            material_type: str = raw_material
        elif unit == "m\u00b2" and any(kw in desc_lower for kw in _FLOORING_KEYWORDS):
            material_type = "Tiles"
            if not item.get("work_category"):
                work_category = "Flooring & Tiling"
        elif any(kw in desc_lower for kw in _PAINTING_KEYWORDS):
            material_type = "Paint/Chemical"
            if not item.get("work_category"):
                work_category = "Painting & Finishes"
        elif "aluminium" in desc_lower or "aluminum" in desc_lower or "glass" in desc_lower:
            material_type = "Aluminium/Glass"
            if not item.get("work_category"):
                work_category = "Doors, Windows & Glazing"
        elif any(kw in desc_lower for kw in ("pvc", "upvc", "pipe", "conduit", "drain")):
            material_type = "PVC/Plastic"
        elif any(kw in desc_lower for kw in ("steel", "iron", "rebar", "tor", "brc", "mesh")):
            material_type = "Steel/Metal"
        else:
            material_type = _SLUG_TO_MATERIAL_TYPE.get(raw_category, "General")

        project_type = _normalise_project_type(project_info.get("building_type"))
        budget_cat = _normalise_budget_category(parameters.get("finish_level"))
        location = str(parameters.get("location") or "Unknown").strip().title()
        soil_type = str(parameters.get("soil_type") or "Ordinary Soil").strip().title()
        roof_type = _normalise_roof_type(parameters.get("roof_type"))
        ceiling_type = _normalise_ceiling_type(parameters.get("ceiling_type"))

        row: dict[str, Any] = {
            "area_imputed":   area_m2,
            "log_area":       log_area,
            "area_per_floor": area_per_floor,
            "log_area_floor": log_area_floor,
            "No. of Floors":  floors,
            "Year":           float(year),
            "is_renovation":  float(is_renovation),
            "Project_Type":   project_type,
            "Budget_Category": budget_cat,
            "Location":       location,
            "Soil_Type":      soil_type,
            "Roof_Type":      roof_type,
            "Ceiling_Type":   ceiling_type,
            "Work_Category":  work_category,
            "Unit":           unit,
            "Material_Type":  material_type,
        }


        X, unknown_names = _build_feature_array(row)

        # ----------------------------------------------------------------
        # Feature completeness: f_m = 1 − (u + d) / max(n, 1)
        # u = unknown categoricals, d = defaulted critical features (area=default)
        # ----------------------------------------------------------------
        n_total = len(art.get("cat_cols", [])) + len(art.get("num_cols", []))
        u = len(unknown_names)
        d = 1 if area_m2 == _NUM_DEFAULTS.get("area_imputed", 200.0) else 0
        feature_completeness = round(max(1.0 - (u + d) / max(n_total, 1), 0.0), 4)

        # ----------------------------------------------------------------
        # Choose model: per-item first, then global
        # ----------------------------------------------------------------
        item_models: dict = art.get("item_models", {})
        item_model = (
            item_models.get(description)
            or item_models.get(description_key)
            or item_models.get(description.strip())
        )

        is_item_level = item_model is not None
        model = item_model if is_item_level else art.get("model")
        model_scope = "item_level" if is_item_level else "global"

        if model is None:
            return {
                "quantity":              0.0,
                "method":                "quantity_predictor",
                "is_item_level":         False,
                "model_scope":           "none",
                "prediction_confidence": 0.0,
                "feature_completeness":  feature_completeness,
                "unknown_feature_count": u,
                "unknown_feature_names": unknown_names,
                "allocation_mode":       "direct",
            }

        log_pred = float(model.predict(X)[0])
        raw_pred = float(np.expm1(log_pred))
        quantity = round(max(raw_pred, 0.0), 2)

        # Scope factor: s_m = 1.0 for item-level, 0.75 for global
        scope_factor = 1.0 if is_item_level else 0.75
        # Prediction confidence = feature_completeness × scope_factor
        prediction_confidence = round(feature_completeness * scope_factor, 4)

        return {
            "quantity":              quantity,
            "method":                "quantity_predictor",
            "is_item_level":         is_item_level,
            "model_scope":           model_scope,
            "prediction_confidence": prediction_confidence,
            "feature_completeness":  feature_completeness,
            "unknown_feature_count": u,
            "unknown_feature_names": unknown_names,
            "allocation_mode":       "direct",
        }

    except Exception:
        return {
            "quantity":              0.0,
            "method":                "quantity_predictor",
            "is_item_level":         False,
            "model_scope":           "error",
            "prediction_confidence": 0.0,
            "feature_completeness":  0.0,
            "unknown_feature_count": 0,
            "unknown_feature_names": [],
            "allocation_mode":       "direct",
        }


# ---------------------------------------------------------------------------
# Normalisation helpers
# ---------------------------------------------------------------------------

# Budget Category — must match label encoder classes exactly (lowercase in v2)
_BUDGET_MAP: dict[str, str] = {
    "extra low budget": "standard",
    "low budget":       "standard",
    "normal":           "standard",
    "standard":         "standard",
    "standard / budget":"standard",
    "budget":           "standard",
    "semi-luxury":      "semi-luxury",
    "semi luxury":      "semi-luxury",
    "semi":             "semi-luxury",
    "luxury":           "luxury",
    "full luxury":      "luxury",
    "full":             "luxury",
    "high":             "luxury",
    "high budget":      "luxury",
}

_ROOF_TYPE_MAP: dict[str, str] = {
    "clay tile":        "clay tile",
    "clay":             "clay tile",
    "tile":             "clay tile",
    "asbestos":         "asbestos sheet",
    "asbestos sheet":   "asbestos sheet",
    "rc flat slab":     "rc flat slab",
    "flat":             "rc flat slab",
    "slab":             "rc flat slab",
    "concrete slab":    "rc flat slab",
    "flat concrete slab":"rc flat slab",
    "flat slab":        "rc flat slab",
}

_CEILING_TYPE_MAP: dict[str, str] = {
    "gypsum":               "gypsum/mineral fibre",
    "gypsum board":         "gypsum/mineral fibre",
    "gypsum/mineral fibre": "gypsum/mineral fibre",
    "mineral fibre":        "gypsum/mineral fibre",
    "pvc":                  "gypsum/mineral fibre",
    "asbestos":             "asbestos flat",
    "asbestos flat":        "asbestos flat",
    "asbestos sheet":       "asbestos flat",
    "timber":               "lunumidella timber",
    "lunumidella timber":   "lunumidella timber",
    "lunumidella":          "lunumidella timber",
    "wood":                 "lunumidella timber",
    "concrete":             "unknown",
    "none":                 "unknown",
    "unknown":              "unknown",
    "not specified":        "unknown",
    "":                     "unknown",
}

_PROJECT_TYPE_MAP: dict[str, str] = {
    "residential house":  "Residential House",
    "residential":        "Residential House",
    "house":              "Residential House",
    "luxury residential": "Luxury Residential House",
    "luxury house":       "Luxury Residential House",
    "apartment":          "Apartment Building",
    "apartment building": "Apartment Building",
    "flat":               "Apartment Building",
    "commercial":         "Commercial Building",
    "commercial building":"Commercial Building",
    "office":             "Commercial Building",
    "shop":               "Commercial Building",
    "educational":        "Educational Building",
    "school":             "Educational Building",
    "university":         "Educational Building",
    "healthcare":         "Healthcare Building",
    "hospital":           "Healthcare Building",
    "government":         "Government Building  New",
    "industrial":         "Commercial Building",
    "warehouse":          "Commercial Building",
    "renovation":         "Renovation/Repair",
    "repair":             "Renovation/Repair",
}


def _normalise_budget_category(value: str | None) -> str:
    """Return budget category matching the label encoder training values (lowercase)."""
    raw = str(value or "").strip().lower()
    return _BUDGET_MAP.get(raw, "standard")


def _normalise_project_type(value: str | None) -> str:
    raw = str(value or "").strip().lower()
    return _PROJECT_TYPE_MAP.get(raw, "Residential House")


def _normalise_roof_type(value: str | None) -> str:
    """Return roof type matching label encoder training values (lowercase)."""
    raw = str(value or "").strip().lower()
    if "clay" in raw and "tile" in raw:
        return "clay tile"
    if "asbestos" in raw:
        return "asbestos sheet"
    if "rc" in raw or "r.c" in raw or "slab" in raw or "flat" in raw:
        return "rc flat slab"
    return _ROOF_TYPE_MAP.get(raw, "clay tile")


def _normalise_ceiling_type(value: str | None) -> str:
    """Return ceiling type matching label encoder training values (lowercase)."""
    raw = str(value or "").strip().lower()
    if raw in _CEILING_TYPE_MAP:
        return _CEILING_TYPE_MAP[raw]
    if "gypsum" in raw or "mineral" in raw or "pvc" in raw:
        return "gypsum/mineral fibre"
    if "asbestos" in raw:
        return "asbestos flat"
    if "timber" in raw or "wood" in raw or "lunumidella" in raw:
        return "lunumidella timber"
    return "unknown"


def _parse_area_to_m2(value: Any, default_m2: float = 167.2) -> float:
    """Return the built_up_area in m² (the unit the model was trained on).

    Default 167.2 m² ≈ 1,800 sq ft.
    """
    if value is None:
        return default_m2
    raw = str(value).strip().lower()
    match = re.search(r"[\d.]+", raw)
    if not match:
        return default_m2
    try:
        num = float(match.group())
    except ValueError:
        return default_m2
    if "m2" in raw or "m²" in raw or "sqm" in raw or "sq m" in raw:
        return round(num, 2)
    if "sq ft" in raw or "sqft" in raw or "ft" in raw:
        return round(num * 0.092903, 2)
    # Heuristic: values above 300 are almost certainly sq ft
    if num > 300:
        return round(num * 0.092903, 2)
    return round(num, 2)  # assume m²


def _coerce_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# Tier-2 cascade: category-level ML prediction + item distribution
# ---------------------------------------------------------------------------

def predict_category_total(
    category_slug: str,
    project_info: dict[str, Any],
    geometry: dict | None = None,
) -> dict[str, Any]:
    """Predict the aggregate quantity for an entire category using the global ML model.

    Returns
    -------
    dict with keys:
        category_total     : float — predicted total quantity for the category
        unit               : str   — most common unit for this category
        confidence         : float — feature_completeness × 0.75 (global scope)
        is_category_level  : True
    """
    _try_load_quantity_predictor()
    if _artifact is None:
        return {
            "category_total":    0.0,
            "unit":              _SLUG_TO_DEFAULT_UNIT.get(category_slug, "m²"),
            "confidence":        0.0,
            "is_category_level": True,
        }

    try:
        import numpy as np  # type: ignore[import]

        unit = _SLUG_TO_DEFAULT_UNIT.get(category_slug, "m²")
        synthetic_item: dict[str, Any] = {
            "category":    category_slug,
            "unit":        unit,
            "description": category_slug,
        }
        # Reuse the standard item-level prediction path; treat its output as
        # the category total when the per-item model is absent (global scope).
        ml = _predict_with_quantity_predictor(synthetic_item, project_info)
        category_total = float(ml.get("quantity") or 0.0)
        completeness = float(ml.get("feature_completeness") or 0.0)
        confidence = round(completeness * 0.75, 4)

        return {
            "category_total":    max(category_total, 0.0),
            "unit":              unit,
            "confidence":        confidence,
            "is_category_level": True,
        }
    except Exception:
        return {
            "category_total":    0.0,
            "unit":              _SLUG_TO_DEFAULT_UNIT.get(category_slug, "m²"),
            "confidence":        0.0,
            "is_category_level": True,
        }


# QS heuristic weights used by `_resolve_distribution_weights`. Kept independent
# of `service._get_qs_weight` to avoid an import cycle.
_QS_DISTRIBUTION_RULES: dict[str, list[tuple[str, float]]] = {
    "concrete_works": [
        ("slab", 40.0), ("beam", 25.0), ("column", 20.0), ("stair", 15.0),
        ("lintel", 5.0), ("grade 20", 35.0), ("grade 25", 35.0), ("concrete", 30.0),
    ],
    "formwork": [
        ("formwork", 30.0), ("shuttering", 30.0), ("mould", 10.0),
    ],
    "reinforcement": [
        ("reinforcement", 30.0), ("tor steel", 30.0), ("mild steel", 25.0), ("brc mesh", 20.0),
    ],
    "brick_masonry": [
        ("9", 70.0), ("225", 70.0), ("4.5", 30.0), ("112", 30.0),
        ("brick", 50.0), ("block", 50.0),
    ],
    "flooring_and_tiling": [
        ("floor", 50.0), ("tile", 50.0), ("skirting", 10.0),
    ],
    "plastering_and_rendering": [
        ("plaster", 40.0), ("render", 35.0), ("skim", 30.0),
        ("wall", 40.0), ("internal", 30.0), ("external", 20.0),
    ],
    "painting_and_finishes": [
        ("paint", 30.0), ("emulsion", 25.0), ("primer", 20.0), ("enamel", 15.0),
        ("weathershield", 20.0), ("wax", 10.0), ("preserv", 10.0),
        ("woodwork", 15.0), ("steelwork", 10.0), ("grille", 10.0),
    ],
    "roofing_and_ceiling": [
        ("timber", 50.0), ("framework", 50.0), ("tile", 40.0), ("sheet", 40.0),
        ("ridge", 5.0), ("valance", 5.0), ("gutter", 5.0), ("downpipe", 5.0),
        ("asbestos", 40.0), ("ceiling", 10.0), ("soffit", 10.0),
    ],
    "sanitary_and_plumbing": [
        ("water closet", 20.0), ("wc", 20.0), ("pipe", 20.0), ("shower", 15.0),
        ("basin", 15.0), ("sink", 10.0), ("tank", 10.0), ("tap", 5.0),
        ("gully", 5.0),
    ],
    "electrical_and_mechanical": [
        ("light", 30.0), ("socket", 25.0), ("cable", 15.0), ("wire", 15.0),
        ("switch", 10.0), ("fan", 10.0), ("distribution board", 5.0),
        ("db", 5.0), ("floodlight", 20.0), ("led", 15.0),
    ],
    "piling_and_substructure": [
        ("excavat", 40.0), ("footing", 40.0), ("foundation", 40.0), ("rubble", 30.0),
        ("backfill", 30.0), ("earth", 30.0), ("concrete", 20.0), ("screed", 15.0),
        ("pcc", 15.0), ("sand", 15.0), ("river sand", 18.0),
        ("cement pot", 10.0),
    ],
    "excavation_and_earthwork": [
        ("clear", 50.0), ("excavat", 50.0), ("trench", 40.0), ("transport", 20.0),
    ],
    "external_and_civil_works": [
        ("paving", 30.0), ("fence", 30.0), ("gate", 20.0), ("road", 20.0),
    ],
    "doors_windows_and_glazing": [
        ("window", 40.0), ("casement", 40.0), ("glaz", 35.0), ("door", 35.0),
    ],
    "demolition_and_removal": [
        ("brick wall", 50.0), ('9" brick', 50.0), ("drain", 30.0),
        ("demolit", 40.0), ("remov", 30.0),
    ],
}


def _qs_weight_for(category: str, description: str) -> float:
    desc = str(description).lower()
    for keyword, weight in _QS_DISTRIBUTION_RULES.get(category, []):
        if keyword in desc:
            return weight
    return 10.0


def _resolve_distribution_weights(
    items: list[dict[str, Any]],
    geometry: dict[str, Any] | None,
) -> tuple[list[float], str]:
    """Return ``(weight_list, method_name)`` for distributing a total across items.

    Priority:
      1. per_floor_area × qs_weight  (both axes vary)
      2. per_floor_area              (only floor varies)
      3. qs_weight                   (only description varies)
      4. equal_split                 (fallback)
    """
    if not items:
        return [], "equal_split"

    per_floor_area: dict[str, float] = {}
    if geometry:
        # Geometry dict may carry per-floor area breakdown alongside totals.
        raw = geometry.get("per_floor_area_m2") or {}
        if isinstance(raw, dict):
            per_floor_area = {str(k): float(v) for k, v in raw.items()}

    categories = [str(it.get("category") or "misc").lower() for it in items]
    descriptions = [str(it.get("description") or "") for it in items]
    floor_scopes = [str(it.get("floor_scope") or "all") for it in items]

    qs_weights = [_qs_weight_for(cat, desc) for cat, desc in zip(categories, descriptions)]
    qs_varies = len(set(qs_weights)) > 1

    all_have_known_floor = bool(per_floor_area) and all(
        fs != "all" and fs in per_floor_area for fs in floor_scopes
    )
    if all_have_known_floor:
        floor_weights = [per_floor_area[fs] for fs in floor_scopes]
        floor_varies = len(set(round(w, 4) for w in floor_weights)) > 1
    else:
        floor_weights = None
        floor_varies = False

    if floor_weights is not None and floor_varies and qs_varies:
        combined = [fw * qw for fw, qw in zip(floor_weights, qs_weights)]
        return combined, "per_floor_area_x_qs_weight"
    if floor_weights is not None and floor_varies:
        return floor_weights, "per_floor_area"
    if qs_varies:
        return qs_weights, "qs_weight"
    return [1.0] * len(items), "equal_split"


def distribute_category_to_items(
    category_total: float,
    category_confidence: float,
    items: list[dict[str, Any]],
    geometry: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Distribute *category_total* across *items* proportional to resolved weights.

    Returns shallow copies of the input items annotated with Tier-2 metadata —
    the originals are not mutated.
    """
    weights, method = _resolve_distribution_weights(items, geometry)
    if not weights:
        return [dict(it) for it in items]

    total_weight = sum(weights) or float(len(items))

    result: list[dict[str, Any]] = []
    for item, w in zip(items, weights):
        share = (w / total_weight) if total_weight > 0 else (1.0 / max(len(items), 1))
        item_qty = round(category_total * share, 4)
        new_item = {**item}
        new_item["quantity"]                   = item_qty
        new_item["final_quantity"]             = item_qty
        new_item["quantity_source"]            = "category_distributed"
        new_item["quantity_allocation_method"] = method
        new_item["quantity_confidence_score"]  = round(category_confidence * share, 4)
        new_item["quantity_confidence"]        = new_item["quantity_confidence_score"]
        recon = dict(new_item.get("reconciliation_summary") or {})
        recon["method"] = "category_distribution"
        recon["allocation_note"] = (
            f"Tier-2 category ML total {category_total:.2f} distributed via {method}"
        )
        new_item["reconciliation_summary"] = recon
        result.append(new_item)

    return result

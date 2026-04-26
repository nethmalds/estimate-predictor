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
predict_quantity(item: dict, project_info: dict) -> tuple[float, str, bool]
    Returns (quantity, method_label, is_item_level) where:
    - method_label = ``"quantity_predictor"`` (ML model) or ``"quantity_predictor"`` (no model loaded)
    - is_item_level = True if an item-specific model was used, False if the global model was used.
"""
from __future__ import annotations

import math
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from core.logging.logger import get_logger

logger = get_logger(__name__)

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
        logger.warning("quantity_predictor not found at %s — quantities will be 0", _MODEL_PATH)
        return
    try:
        import joblib  # type: ignore[import]
        _artifact = joblib.load(str(_MODEL_PATH))
        logger.info(
            "quantity_predictor loaded model=%s item_models=%d",
            type(_artifact.get("model")).__name__,
            len(_artifact.get("item_models", {})),
        )
    except Exception:
        logger.exception("quantity_predictor load failed")


def predict_quantity(
    item: dict[str, Any],
    project_info: dict[str, Any],
) -> tuple[float, str, bool]:
    """Predict the quantity for a single BOQ item.

    Uses the real Quantity Predictor if available. Returns (0.0, label, False) if not.
    """
    _try_load_quantity_predictor()

    if _artifact is not None:
        return _predict_with_quantity_predictor(item, project_info)
    return 0.0, "quantity_predictor", False


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


def _build_feature_array(row: dict[str, Any]) -> "Any":  # returns np.ndarray
    """Build the numpy feature vector expected by the model.

    Replicates the notebook's ``encode_input`` helper:
    - Numeric columns are taken directly as floats (with defaults).
    - Categorical columns are integer-encoded using the stored LabelEncoders.
      Unknown values are encoded as 0.
    """
    import numpy as np  # type: ignore[import]

    art = _artifact  # type: ignore[index]
    num_cols: list[str] = art["num_cols"]
    cat_cols: list[str] = art["cat_cols"]
    encoders: dict = art["label_encoders"]

    feats: list[float] = []

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
            logger.debug("quantity_predictor: unknown value col=%s val=%r", col, val)

    return np.array(feats, dtype=float).reshape(1, -1)


def _predict_with_quantity_predictor(
    item: dict[str, Any],
    project_info: dict[str, Any],
) -> tuple[float, str, bool]:
    """Run inference against the loaded quantity_predictor artifact.

    Strategy:
      1. Build feature row from item + project_info.
      2. If the item description matches a per-item model key, use that model.
      3. Otherwise use the global model.
      4. Inverse-transform via np.expm1() (model trained on log1p target).
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

        # Pin to training year — using datetime.now() causes out-of-distribution drift
        year = _TRAINING_YEAR
        is_renovation = 0

        # The item description is used both as a feature and as the per-item model key.
        # BOQ items may store their description in 'description' OR 'Work_Item'.
        description: str = item.get("description") or item.get("Work_Item") or ""
        # Normalise to lowercase+stripped to match notebook's Work_Item keys
        description_key: str = description.strip().lower()

        # Map internal category slug → ML Work_Category label the model was trained on
        raw_category: str = (item.get("category") or "misc").lower()
        work_category: str = _SLUG_TO_WORK_CATEGORY.get(raw_category, "Concrete Works")
        # If item already carries a proper Work_Category string (from BOQ generator), prefer it
        if item.get("work_category"):
            work_category = str(item["work_category"]).strip()

        # Unit: honour item's unit when present; fall back to slug default.
        # Always normalise through _normalise_unit so bytes match the label encoder.
        raw_unit: str = (item.get("unit") or "").strip()
        unit: str = _normalise_unit(raw_unit) if raw_unit else _SLUG_TO_DEFAULT_UNIT.get(raw_category, "m\u00b3")

        # ----------------------------------------------------------------
        # Refine Work_Category and Material_Type based on item description
        # and unit — to match the training data labels more precisely.
        # ----------------------------------------------------------------
        desc_lower = description.lower()

        # Material_Type: honour item value first; then infer from description/category.
        # Values must be exact label encoder classes.
        raw_material: str = (item.get("material_type") or "").strip()
        if raw_material:
            material_type: str = raw_material
        elif unit == "m\u00b2" and any(kw in desc_lower for kw in _FLOORING_KEYWORDS):
            # Floor tiling/screed → use dedicated flooring category
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

        # Normalised project-level categoricals
        project_type = _normalise_project_type(project_info.get("building_type"))
        budget_cat = _normalise_budget_category(parameters.get("finish_level"))
        # Location and Soil_Type: use title-case to match training label format,
        # but only capitalise first letter of each word (already what .title() does).
        location = str(parameters.get("location") or "Unknown").strip().title()
        soil_type = str(parameters.get("soil_type") or "Ordinary Soil").strip().title()
        roof_type = _normalise_roof_type(parameters.get("roof_type"))
        ceiling_type = _normalise_ceiling_type(parameters.get("ceiling_type"))

        # ----------------------------------------------------------------
        # Assemble feature row — must match model's feature_cols exactly
        # ----------------------------------------------------------------
        row: dict[str, Any] = {
            # Numeric
            "area_imputed":   area_m2,
            "log_area":       log_area,
            "area_per_floor": area_per_floor,
            "log_area_floor": log_area_floor,
            "No. of Floors":  floors,
            "Year":           float(year),
            "is_renovation":  float(is_renovation),
            # Categorical
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

        logger.debug(
            "quantity_predictor row: category=%s work_category=%s unit=%s material=%s area=%.1f floors=%d",
            raw_category, work_category, unit, material_type, area_m2, floors,
        )

        X = _build_feature_array(row)

        # ----------------------------------------------------------------
        # Choose model: per-item first (exact key match), then global.
        # The per-item model dict was built from Work_Item strings in the
        # training notebook — try both exact and lowercased description.
        # ----------------------------------------------------------------
        item_models: dict = art.get("item_models", {})
        item_model = (
            item_models.get(description)
            or item_models.get(description_key)
            or item_models.get(description.strip())
        )

        is_item_level = item_model is not None
        model = item_model if is_item_level else art.get("model")

        if model is None:
            logger.warning("quantity_predictor: no global model in bundle")
            return 0.0, "quantity_predictor", False

        # Model was trained on log1p(qty) — inverse with expm1
        log_pred = float(model.predict(X)[0])
        raw_pred = float(np.expm1(log_pred))

        quantity = round(max(raw_pred, 0.0), 2)
        return quantity, "quantity_predictor", is_item_level

    except Exception:
        logger.exception("quantity_predictor inference failed")
        return 0.0, "quantity_predictor", False


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

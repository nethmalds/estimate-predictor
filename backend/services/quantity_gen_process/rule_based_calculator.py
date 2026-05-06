"""Rule-based quantity calculator from floorplan geometry data.

Converts the structured geometry dict (produced by the CV pipeline) into BOQ
item quantities using deterministic construction-industry formulas.

If a rule exists for an item's category, the quantity is returned tagged as
``"geometry"`` or ``"rule_based"``.  If no applicable rule exists, ``None``
is returned — signalling that Quantity Predictor should predict that item's quantity.

Phase 5 addition
-----------------
``calculate_parametric`` provides parameter-driven estimates for use in the
no-floorplan path.  It applies the same formulas as ``calculate_from_geometry``
but sources the area from ``project_info.parameters.built_up_area`` instead
of CV measurements.  Geometry-confirmed values are inherently more reliable;
the parametric path carries lower confidence.
"""
from __future__ import annotations

import math
import re
from typing import Any

# Default floor-to-ceiling height used when geometry doesn't specify it (metres)
_DEFAULT_FLOOR_HEIGHT_M = 3.0


def calculate_from_geometry(
    item: dict[str, Any],
    geometry: dict[str, Any],
    floors: int = 1,
    parameters: dict[str, Any] | None = None,
) -> tuple[float, str] | tuple[None, None]:
    """Attempt to calculate quantity for *item* from *geometry*.

    Returns
    -------
    (quantity, source)
        where ``source`` is ``"geometry"`` (direct CV measurement) or
        ``"rule_based"`` (derived formula from geometry values).
    (None, None)
        when no geometry rule applies — caller should fall back to Quantity Predictor.
    """
    params: dict = parameters or {}
    category: str = (item.get("category") or "misc").lower()

    area_m2: float = float(geometry.get("total_floor_area_m2") or 0.0)
    perimeter_m: float = float(geometry.get("perimeter_m") or 0.0)
    wall_length_m: float = float(geometry.get("wall_length_m") or 0.0)
    opening_count: int = int(geometry.get("opening_count") or 0)
    floor_height: float = _DEFAULT_FLOOR_HEIGHT_M

    # If geometry values are all zero, we have nothing useful
    if area_m2 == 0.0 and wall_length_m == 0.0 and opening_count == 0:
        return None, None

    floor_count = max(int(floors or 1), 1)
    bedrooms = _coerce_int(params.get("bedrooms")) or 2
    bathrooms = _coerce_int(params.get("bathrooms")) or 1

    return _apply_category_rules(
        category, area_m2, wall_length_m, perimeter_m, opening_count,
        floor_count, floor_height, bedrooms, bathrooms
    )


def calculate_parametric(
    item: dict[str, Any],
    project_info: dict[str, Any],
) -> tuple[float, str] | tuple[None, None]:
    """Parameter-driven quantity estimate for use in the no-floorplan path (Phase 5).

    Uses ``project_info.parameters.built_up_area`` as the area source.
    All geometry-confirming heuristics are still applied but at lower confidence
    (callers should assign weight ``"parametric"`` rather than ``"geometry"``).

    Returns
    -------
    (quantity, "parametric")
        when a parameter-driven estimate is possible.
    (None, None)
        when the category has no parameter-driven rule.
    """
    params: dict = (project_info.get("parameters") or {})
    category: str = (item.get("category") or "misc").lower()

    # Derive area from project parameters
    area_m2 = _parse_area_to_m2_from_params(params.get("built_up_area"))
    if area_m2 <= 0:
        return None, None

    floor_count = max(int(project_info.get("floors") or 1), 1)
    floor_height = _DEFAULT_FLOOR_HEIGHT_M
    bedrooms = _coerce_int(params.get("bedrooms")) or 2
    bathrooms = _coerce_int(params.get("bathrooms")) or 1

    # Estimate perimeter and wall_length from area (same heuristics as pipeline)
    perimeter_m = 4.0 * math.sqrt(area_m2)
    internal_wall_estimate = perimeter_m * 0.6
    wall_length_m = perimeter_m + internal_wall_estimate

    # Opening count: rough estimate from bedrooms and bathrooms
    opening_count = max((bedrooms * 2) + (bathrooms * 1) + 2, 4)

    result = _apply_category_rules(
        category, area_m2, wall_length_m, perimeter_m, opening_count,
        floor_count, floor_height, bedrooms, bathrooms
    )
    if result[0] is None:
        return None, None
    return result[0], "parametric"


# ---------------------------------------------------------------------------
# Shared rule engine
# ---------------------------------------------------------------------------

def _apply_category_rules(
    category: str,
    area_m2: float,
    wall_length_m: float,
    perimeter_m: float,
    opening_count: int,
    floor_count: int,
    floor_height: float,
    bedrooms: int,
    bathrooms: int,
) -> tuple[float, str] | tuple[None, None]:
    """Apply per-category construction formulas.

    Returns (quantity, source) or (None, None) when no rule applies.
    The source tag is 'geometry' (direct CV measurement) or 'rule_based'
    (derived formula). For the parametric path the caller overrides to
    'parametric'.
    """
    if category == "preliminary_and_general":
        return 1.0, "rule_based"

    if category in ("excavation_and_earthwork", "demolition_and_removal"):
        if area_m2 > 0:
            return round(area_m2 * 1.15, 2), "geometry"
        return None, None

    if category == "piling_and_substructure":
        if area_m2 > 0:
            return round(area_m2 * floor_count * 0.6, 2), "rule_based"
        return None, None

    if category == "concrete_works":
        if area_m2 > 0:
            return round(area_m2 * floor_count * 0.12, 2), "rule_based"
        return None, None

    if category == "formwork":
        if area_m2 > 0:
            return round(area_m2 * floor_count * 0.75, 2), "rule_based"
        return None, None

    if category == "reinforcement":
        if area_m2 > 0:
            return round(area_m2 * floor_count * 12.5, 2), "rule_based"
        return None, None

    if category == "brick_masonry":
        if wall_length_m > 0:
            opening_area = opening_count * 2.0
            wall_face_area = wall_length_m * floor_height * floor_count
            return round(max(wall_face_area - opening_area, 0), 2), "geometry"
        if area_m2 > 0:
            return round(area_m2 * floor_count * 0.65, 2), "rule_based"
        return None, None

    if category in ("plastering_and_rendering", "painting_and_finishes"):
        if wall_length_m > 0:
            return round(wall_length_m * floor_height * floor_count * 2, 2), "geometry"
        if area_m2 > 0:
            return round(area_m2 * floor_count * 1.1, 2), "rule_based"
        return None, None

    if category == "flooring_and_tiling":
        if area_m2 > 0:
            return round(area_m2 * floor_count * 1.05, 2), "geometry"
        return None, None

    if category == "roofing_and_ceiling":
        if area_m2 > 0:
            return round(area_m2 * 1.05, 2), "geometry"
        return None, None

    if category == "doors_windows_and_glazing":
        if opening_count > 0:
            return float(opening_count), "geometry"
        qty = max((bedrooms * 2.0) + (bathrooms * 1.5) + 2.0, 4.0)
        return round(qty, 2), "rule_based"

    if category == "electrical_and_mechanical":
        if area_m2 > 0:
            return round(max((area_m2 / 15.0) * floor_count, 6.0), 2), "rule_based"
        return None, None

    if category == "sanitary_and_plumbing":
        qty = max((bathrooms * 4.0) + (bedrooms * 1.5), 4.0)
        return round(qty, 2), "rule_based"

    if category == "external_and_civil_works":
        if area_m2 > 0:
            return round(area_m2 * 0.25, 2), "rule_based"
        return None, None

    return None, None


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _coerce_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _parse_area_to_m2_from_params(value: Any) -> float:
    """Parse built_up_area from project parameters to m².

    Accepts numbers or strings like "150 m2", "1615 sqft".
    """
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    txt = str(value).lower().strip()
    # Extract numeric part
    m = re.search(r"[\d,]+\.?\d*", txt)
    if not m:
        return 0.0
    num = float(m.group(0).replace(",", ""))
    if "sqft" in txt or "sq ft" in txt or "ft" in txt:
        return num * 0.0929
    return num  # assume m²

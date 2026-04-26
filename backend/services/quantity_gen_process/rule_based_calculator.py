"""Rule-based quantity calculator from floorplan geometry data.

Converts the structured geometry dict (produced by the CV pipeline) into BOQ
item quantities using deterministic construction-industry formulas.

If a rule exists for an item's category, the quantity is returned tagged as
``"geometry"`` or ``"rule_based"``.  If no applicable rule exists, ``None``
is returned — signalling that Quantity Predictor should predict that item's quantity.
"""
from __future__ import annotations

import math
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

    # --- Per-category rules ----------------------------------------------

    if category == "preliminaries":
        # Always 1 (lump sum item — not geometry-driven)
        return 1.0, "rule_based"

    if category == "site":
        if area_m2 > 0:
            return round(area_m2 * 1.15, 2), "geometry"   # 15% clearance margin
        return None, None

    if category == "foundation":
        if area_m2 > 0:
            return round(area_m2 * floor_count * 0.6, 2), "rule_based"
        return None, None

    if category == "structure":
        if area_m2 > 0:
            return round(area_m2 * floor_count * 0.75, 2), "rule_based"
        return None, None

    if category == "masonry":
        if wall_length_m > 0:
            # Both sides of wall, minus openings (each ~2 m²)
            opening_area = opening_count * 2.0
            wall_face_area = wall_length_m * floor_height * floor_count
            return round(max(wall_face_area - opening_area, 0), 2), "geometry"
        if area_m2 > 0:
            return round(area_m2 * floor_count * 0.65, 2), "rule_based"
        return None, None

    if category == "finishes":
        if wall_length_m > 0:
            # Both sides of all walls, two coats
            return round(wall_length_m * floor_height * floor_count * 2, 2), "geometry"
        if area_m2 > 0:
            return round(area_m2 * floor_count * 1.1, 2), "rule_based"
        return None, None

    if category == "roof":
        if area_m2 > 0:
            return round(area_m2 * 1.05, 2), "geometry"
        return None, None

    if category == "openings":
        if opening_count > 0:
            return float(opening_count), "geometry"
        # Fallback estimate
        qty = max((bedrooms * 2.0) + (bathrooms * 1.5) + 2.0, 4.0)
        return round(qty, 2), "rule_based"

    if category == "electrical":
        if area_m2 > 0:
            # ~1 light/socket per 15 m² per floor
            return round(max((area_m2 / 15.0) * floor_count, 6.0), 2), "rule_based"
        return None, None

    if category == "plumbing":
        # Plumbing is fixtures-driven, not area-driven
        qty = max((bathrooms * 4.0) + (bedrooms * 1.5), 4.0)
        return round(qty, 2), "rule_based"

    if category == "external":
        if area_m2 > 0:
            return round(area_m2 * 0.25, 2), "rule_based"
        return None, None

    # No rule for this category — signal Quantity Predictor
    return None, None


def _coerce_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None

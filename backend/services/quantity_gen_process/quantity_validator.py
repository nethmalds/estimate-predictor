"""Post-fusion quantity validation and sanity checks.

Applies per-category bounds — expressed as multipliers of the total floor area
(area_m2 × floor_count) — to detect improbable quantities.  Items outside the
acceptable range are flagged with a ``"quantity_warning"`` field and can
optionally be clamped to the nearest bound.

Bounds table
------------
Each entry is ``(lo_ratio, hi_ratio)`` where the expected quantity lies in the
range ``[lo_ratio × total_area, hi_ratio × total_area]``.  ``None`` means no
bound in that direction.  The ratios are intentionally generous — the goal is
to catch extreme outliers only, not to second-guess reasonable estimates.

  Category                     lo     hi   Unit hint
  ─────────────────────────────────────────────────────
  concrete_works               0.005  0.60  m³ / m²
  formwork                     0.05   3.00  m² / m²
  reinforcement                1.0   50.0   kg / m²
  brick_masonry                0.05   6.00  m² / m²  (wall face area)
  plastering_and_rendering     0.10   8.00  m² / m²
  painting_and_finishes        0.10   8.00  m² / m²
  flooring_and_tiling          0.20   2.50  m² / m²
  roofing_and_ceiling          0.20   2.50  m² / m²
  doors_windows_and_glazing    None   0.25  openings / m²
  electrical_and_mechanical    None   0.30  fixtures  / m²
  sanitary_and_plumbing        None   0.15  fixtures  / m²
  excavation_and_earthwork     0.05   3.00  m³ / m²
  piling_and_substructure      0.05   3.00  m³ / m²
  external_and_civil_works     0.01   1.50  m² / m²
"""
from __future__ import annotations

import math

from core.logging.logger import get_logger

logger = get_logger(__name__)

# (lo_multiplier, hi_multiplier) relative to total_floor_area_m2 × floor_count.
# None means no lower / upper bound in that direction.
_BOUNDS: dict[str, tuple[float | None, float | None]] = {
    "concrete_works":           (0.005, 0.60),
    "formwork":                 (0.05,  3.00),
    "reinforcement":            (1.0,  50.0),
    "brick_masonry":            (0.05,  6.00),
    "plastering_and_rendering": (0.10,  8.00),
    "painting_and_finishes":    (0.10,  8.00),
    "flooring_and_tiling":      (0.20,  2.50),
    "roofing_and_ceiling":      (0.20,  2.50),
    "doors_windows_and_glazing":(None,  0.25),
    "electrical_and_mechanical":(None,  0.30),
    "sanitary_and_plumbing":    (None,  0.15),
    "excavation_and_earthwork": (0.05,  3.00),
    "piling_and_substructure":  (0.05,  3.00),
    "external_and_civil_works": (0.01,  1.50),
}


def validate_quantity(
    item: dict,
    geometry: dict | None,
    floors: int = 1,
    *,
    clamp: bool = False,
) -> dict:
    """Validate and optionally clamp an item's quantity.

    Modifies *item* in-place and returns it.

    Rules applied
    -------------
    1. Negative quantities are clamped to 0 unconditionally.
    2. Zero quantities are flagged (``"zero_quantity"``).
    3. When a geometry dict with a valid floor area is available, the
       quantity is checked against per-category bounds.

    Parameters
    ----------
    item:
        BOQ item dict with at least ``quantity`` and ``category`` fields.
    geometry:
        Geometry dict from the CV pipeline, or ``None``.
    floors:
        Number of floors (used to scale the reference area).
    clamp:
        When ``True``, quantities outside the bounds are adjusted to the
        nearest bound in addition to being flagged.

    Returns
    -------
    The same *item* dict, possibly with a ``"quantity_warning"`` field added
    and ``"quantity"`` adjusted (when *clamp* is ``True``).
    """
    qty = float(item.get("quantity") or 0.0)
    category = (item.get("category") or "misc").lower()

    # ── Rule 1: negative → clamp to zero ─────────────────────────────────────
    if qty < 0:
        item["quantity"] = 0.0
        item["quantity_warning"] = "negative_clamped_to_zero"
        logger.debug("quantity_validator clamped negative qty item=%s", item.get("description", ""))
        return item

    # ── Rule 2: zero quantity ────────────────────────────────────────────────
    if qty == 0.0:
        item["quantity_warning"] = "zero_quantity"
        return item

    # ── Rule 3: bounds check against floor area ──────────────────────────────
    area_m2 = float((geometry or {}).get("total_floor_area_m2") or 0.0)
    if area_m2 <= 0 or category not in _BOUNDS:
        return item  # cannot validate without a reference area or known category

    total_area = area_m2 * max(floors, 1)
    lo_ratio, hi_ratio = _BOUNDS[category]

    lo = (lo_ratio * total_area) if lo_ratio is not None else None
    hi = (hi_ratio * total_area) if hi_ratio is not None else None

    warning_parts: list[str] = []

    if lo is not None and qty < lo:
        warning_parts.append(f"below_lower_bound({lo:.2f})")
        if clamp:
            item["quantity"] = round(lo, 2)

    if hi is not None and qty > hi:
        warning_parts.append(f"above_upper_bound({hi:.2f})")
        if clamp:
            item["quantity"] = round(hi, 2)

    if warning_parts:
        item["quantity_warning"] = "; ".join(warning_parts)
        logger.debug(
            "quantity_validator flagged item=%s category=%s qty=%.2f warning=%s",
            item.get("description", ""),
            category,
            qty,
            item["quantity_warning"],
        )

    # ── Phase 12 additions ────────────────────────────────────────────────────

    # Rule 4: discrete unit non-whole-number check
    _check_discrete_unit(item)

    # Rule 5: disagreement score threshold check
    _check_disagreement_score(item)

    return item


# ---------------------------------------------------------------------------
# Phase 12 — extended validators
# ---------------------------------------------------------------------------

_DISCRETE_UNITS: frozenset[str] = frozenset({"nr", "nr.", "no", "no.", "item", "pair", "set", "each", "lot"})
_HIGH_DISAGREEMENT_THRESHOLD = 0.50


def _check_discrete_unit(item: dict) -> None:
    """Flag discrete-unit items whose quantity is not a whole number (Phase 12)."""
    unit = str(item.get("unit") or item.get("preferred_unit") or "").lower().strip()
    if unit not in _DISCRETE_UNITS:
        return
    qty = float(item.get("quantity") or 0.0)
    if qty != math.floor(qty):
        existing = item.get("quantity_warning", "")
        flag = "non_integer_discrete_quantity"
        item["quantity_warning"] = f"{existing}; {flag}" if existing else flag
        logger.debug("quantity_validator discrete_non_integer item=%s qty=%.3f unit=%s",
                     item.get("description", ""), qty, unit)


def _check_disagreement_score(item: dict) -> None:
    """Flag items with high candidate disagreement score (Phase 12)."""
    summary = item.get("reconciliation_summary") or {}
    delta = float(summary.get("disagreement_score") or 0.0)
    if delta > _HIGH_DISAGREEMENT_THRESHOLD:
        existing = item.get("quantity_warning", "")
        flag = f"high_candidate_disagreement({delta:.2f})"
        item["quantity_warning"] = f"{existing}; {flag}" if existing else flag


def validate_relational_checks(
    items: list[dict],
    geometry: dict | None = None,
    project_info: dict | None = None,
) -> list[str]:
    """Phase 12: cross-item relational validation.

    Checks:
    - Floor finishes quantity vs floor area
    - Wall finishes quantity vs wall area
    - Opening count vs number of rooms (bedrooms + bathrooms + 1)
    - Plumbing fixtures vs bedrooms/bathrooms count

    Returns a list of warning strings.
    """
    import math as _math

    warnings: list[str] = []
    if not items:
        return warnings

    geo = geometry or {}
    params = (project_info or {}).get("parameters") or {}
    area_m2 = float(geo.get("total_floor_area_m2") or 0.0)
    wall_length_m = float(geo.get("wall_length_m") or 0.0)
    opening_count = int(geo.get("opening_count") or 0)
    floors = max(int((project_info or {}).get("floors") or 1), 1)
    bedrooms = int(params.get("bedrooms") or 2)
    bathrooms = int(params.get("bathrooms") or 1)
    expected_rooms = bedrooms + bathrooms + 1  # +1 for living room

    # Aggregate quantities by category
    qty_by_cat: dict[str, float] = {}
    for item in items:
        cat = (item.get("category") or "misc").lower()
        qty = float(item.get("quantity") or 0.0)
        qty_by_cat[cat] = qty_by_cat.get(cat, 0.0) + qty

    # Check 1: floor finishes vs floor area
    if area_m2 > 0:
        flooring_qty = qty_by_cat.get("flooring_and_tiling", 0.0)
        expected_floor = area_m2 * floors
        if flooring_qty > 0 and flooring_qty > expected_floor * 3.0:
            warnings.append(
                f"flooring_and_tiling qty={flooring_qty:.1f} far exceeds expected floor area {expected_floor:.1f} m²"
            )
        if flooring_qty > 0 and flooring_qty < expected_floor * 0.1:
            warnings.append(
                f"flooring_and_tiling qty={flooring_qty:.1f} seems too low for floor area {expected_floor:.1f} m²"
            )

    # Check 2: wall finishes vs wall area
    if wall_length_m > 0:
        wall_area = wall_length_m * 3.0 * floors * 2  # both sides
        for cat in ("plastering_and_rendering", "painting_and_finishes"):
            cat_qty = qty_by_cat.get(cat, 0.0)
            if cat_qty > 0 and cat_qty > wall_area * 3.0:
                warnings.append(
                    f"{cat} qty={cat_qty:.1f} far exceeds estimated wall area {wall_area:.1f} m²"
                )

    # Check 3: opening/glazing count vs room count
    if opening_count > 0 or expected_rooms > 0:
        glazing_qty = qty_by_cat.get("doors_windows_and_glazing", 0.0)
        max_expected_openings = expected_rooms * 4.0
        if glazing_qty > max_expected_openings:
            warnings.append(
                f"doors_windows_and_glazing qty={glazing_qty:.1f} exceeds estimated max openings {max_expected_openings:.0f} for {expected_rooms} rooms"
            )

    # Check 4: plumbing vs bedrooms/bathrooms
    plumbing_qty = qty_by_cat.get("sanitary_and_plumbing", 0.0)
    expected_plumbing_min = bathrooms * 2
    expected_plumbing_max = (bathrooms * 6) + (bedrooms * 2) + 5
    if plumbing_qty > 0 and plumbing_qty > expected_plumbing_max:
        warnings.append(
            f"sanitary_and_plumbing qty={plumbing_qty:.1f} seems high for {bedrooms}bed/{bathrooms}bath (max ~{expected_plumbing_max})"
        )

    return warnings

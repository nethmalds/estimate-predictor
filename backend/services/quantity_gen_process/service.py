"""Quantity Take-Off Engine — branching compute logic.

Stage decomposition (Phase 4):
  1. Candidate generation — collect all available quantity estimates per item.
  2. Reconciliation        — fuse candidates with unit-aware confidence weighting.
  3. Validation            — post-reconciliation quality checks.
  4. Unit dimensionality   — IMP-QTY-02: validate quantity against BSR unit dimensionality.

Branch A (floorplan geometry available):
  Candidate sources: geometry / rule_based  +  ML (item-level fused in, global for fallback).
  Tags: ``quantity_source`` = ``"geometry"`` | ``"rule_based"`` | ``"quantity_predictor"``

Branch B (no floorplan):
  Candidate sources: parametric (parameter-driven rules)  +  ML.
  Tags: ``quantity_source`` = ``"parametric"`` | ``"quantity_predictor"``

Extra per-item fields:
  ``quantity_confidence_score``, ``quantity_candidates``,
  ``reconciliation_summary``, ``quantity_warning`` (from validator)
"""
from __future__ import annotations

from typing import Any

from services.quantity_gen_process.rule_based_calculator import (
    calculate_from_geometry,
    calculate_parametric,
)
from services.quantity_gen_process.quantity_calculator import predict_quantity
from services.quantity_gen_process.confidence_scoring import (
    score_geometry_confidence,
    fuse_candidates,
    candidate_weight,
)
from services.quantity_gen_process.quantity_validator import validate_quantity


# Categories whose quantity is a QS convention (lump sum = 1.0) — skip ML fusion.
_LUMP_SUM_CATEGORIES: frozenset[str] = frozenset({
    "preliminary_and_general",
    "miscellaneous",
    "other",
    "testing_and_commissioning",
})


# ---------------------------------------------------------------------------
# IMP-QTY-02: Unit dimensionality validation
# ---------------------------------------------------------------------------

# Mapping: category → expected dimensionality ("volume", "area", "length", "count", "mass", "lump")
_CATEGORY_DIMENSIONALITY: dict[str, str] = {
    "excavation_and_earthwork":  "volume",   # m³
    "piling_and_substructure":   "volume",   # m³
    "concrete_works":            "volume",   # m³
    "formwork":                  "area",     # m²
    "reinforcement":             "mass",     # kg
    "brick_masonry":             "area",     # m²
    "plastering_and_rendering":  "area",     # m²
    "painting_and_finishes":     "area",     # m²
    "roofing_and_ceiling":       "area",     # m²
    "flooring_and_tiling":       "area",     # m²
    "external_and_civil_works":  "area",     # m²
    "demolition_and_removal":    "area",     # m²
    "doors_windows_and_glazing": "count",    # Nr
    "sanitary_and_plumbing":     "count",    # Nr
    "electrical_and_mechanical": "count",    # Nr
    "preliminary_and_general":   "lump",     # Item
    "testing_and_commissioning": "lump",     # Item
    "miscellaneous":             "lump",     # Item
}

# Unit → dimensionality
_UNIT_DIMENSIONALITY: dict[str, str] = {
    "m³": "volume", "m3": "volume", "cum": "volume",
    "m²": "area",   "m2": "area",   "sqm": "area",
    "m":  "length",  "lm": "length", "rm": "length", "lineal m": "length",
    "nr": "count",   "nr.": "count", "no": "count",  "no.": "count",
    "each": "count", "set": "count", "pair": "count",
    "kg":  "mass",   "kg.": "mass",  "ton": "mass",  "tonne": "mass",
    "item": "lump",  "sum": "lump",  "lot": "lump",  "allow": "lump",
}


def _unit_dimensionality(unit: str) -> str | None:
    """Return the dimensionality category for a given unit string."""
    return _UNIT_DIMENSIONALITY.get(unit.lower().strip())


def _validate_quantity_against_unit(item: dict) -> dict:
    """IMP-QTY-02: Validate that the computed quantity is consistent with the BSR unit.

    If the category expects a volume (m³) but the BSR unit is m (length), the
    quantity is likely wrong.  In that case we flag the item with a warning and
    reduce its quantity_confidence_score by 0.30 rather than silently passing.
    """
    unit = (item.get("unit") or item.get("preferred_unit") or "").strip()
    category = (item.get("category") or "misc").lower()
    quantity = float(item.get("quantity") or 0.0)

    expected_dim = _CATEGORY_DIMENSIONALITY.get(category)
    actual_dim = _unit_dimensionality(unit)

    if expected_dim and actual_dim and expected_dim != actual_dim:
        existing_warning = item.get("quantity_warning") or ""
        mismatch_msg = (
            f"Unit dimensionality mismatch: category '{category}' expects "
            f"'{expected_dim}' but BSR unit '{unit}' is '{actual_dim}'. "
            "Quantity may be unreliable."
        )
        item["quantity_warning"] = (existing_warning + " | " + mismatch_msg).strip(" | ")
        # Downgrade confidence
        current_conf = float(item.get("quantity_confidence_score") or 0.5)
        item["quantity_confidence_score"] = max(0.0, round(current_conf - 0.30, 4))
        item["quantity_confidence"] = item["quantity_confidence_score"]
        # Flag for review
        item["needs_rate_review"] = True

    return item


def compute_quantities(
    boq_items: list[dict],
    project_info: dict,
    floorplan_geometry: dict | None = None,
) -> list[dict]:
    """Compute quantities for all BOQ items using the appropriate branch.

    Parameters
    ----------
    boq_items:
        Final BOQ item list (each dict has at least ``category``).
    project_info:
        Normalised project info (floors, parameters, etc.).
    floorplan_geometry:
        Structured geometry dict from the CV pipeline, or ``None``.

    Returns
    -------
    list[dict]
        Each item enriched with ``quantity``, ``quantity_source``,
        ``quantity_confidence_score``, and (for geometry branch) optional
        ``quantity_candidates`` and ``quantity_warning`` fields.
    """
    parameters: dict = project_info.get("parameters") or {}
    floors: int = max(int(project_info.get("floors") or 1), 1)

    has_geometry = _geometry_is_usable(floorplan_geometry)

    if has_geometry:
        result = _compute_with_geometry(boq_items, project_info, floorplan_geometry, floors, parameters)
    else:
        result = _compute_quantity_predictor_all(boq_items, project_info)

    # IMP-QTY-02: validate each item's quantity against its BSR unit dimensionality
    return [_validate_quantity_against_unit(item) for item in result]


# ---------------------------------------------------------------------------
# Branch A — Floorplan available
# ---------------------------------------------------------------------------

def _compute_with_geometry(
    boq_items: list[dict],
    project_info: dict,
    geometry: dict,
    floors: int,
    parameters: dict,
) -> list[dict]:
    # Stage 1: compute geometry confidence (feeds reconciliation weights)
    geo_conf = score_geometry_confidence(geometry)

    computed: list[dict] = []
    quantity_predictor_needed: list[dict] = []

    for item in boq_items:
        category = (item.get("category") or "misc").lower()
        item_unit = item.get("unit") or item.get("preferred_unit") or ""

        # ── Stage 1: candidate generation ───────────────────────────────
        geo_qty, geo_source = calculate_from_geometry(
            item,
            geometry,
            floors=floors,
            parameters=parameters,
        )
        item_copy = dict(item)

        if geo_qty is not None:
            # We have a geometry/rule candidate
            candidates: list[tuple[float, str, bool]] = [(geo_qty, geo_source, False)]
            ml_diag: dict = {}

            if category not in _LUMP_SUM_CATEGORIES:
                # Stage 1 (continued): ML candidate generation
                ml_result = predict_quantity(item, project_info)
                ml_qty = ml_result["quantity"]
                is_item_level = ml_result["is_item_level"]
                ml_diag = ml_result
                if is_item_level and ml_qty > 0:
                    candidates.append((ml_qty, "quantity_predictor", True))

            # ── Stage 2: reconciliation ──────────────────────────────────
            fused_qty, conf, dominant_src, cands_meta = fuse_candidates(
                candidates, geo_conf, unit=item_unit, ml_diagnostics=ml_diag
            )

            # Build Phase 3 reconciliation summary
            item_copy["quantity"]               = fused_qty
            item_copy["final_quantity"]         = fused_qty
            item_copy["quantity_source"]        = dominant_src
            item_copy["quantity_confidence_score"] = conf
            item_copy["quantity_confidence"]    = conf
            item_copy["quantity_candidates"]    = cands_meta
            item_copy["reconciliation_summary"] = _build_reconciliation_summary(
                cands_meta, fused_qty, dominant_src, item_unit
            )

            # ── Stage 3: per-item validation ────────────────────────────
            item_copy = validate_quantity(item_copy, geometry, floors)
            computed.append(item_copy)
        else:
            quantity_predictor_needed.append(item_copy)

    if quantity_predictor_needed:
        _resolve_quantity_predictor_items(quantity_predictor_needed, project_info, geo_conf, geometry, floors)
        computed.extend(quantity_predictor_needed)

    geo_count = len(boq_items) - len(quantity_predictor_needed)
    return computed


# ---------------------------------------------------------------------------
# Branch B — No floorplan (Phase 5)
# ---------------------------------------------------------------------------

def _compute_quantity_predictor_all(
    boq_items: list[dict],
    project_info: dict,
) -> list[dict]:
    """No-floorplan path: parametric candidates + ML candidates, then reconcile."""
    computed: list[dict] = [dict(item) for item in boq_items]
    parameters = project_info.get("parameters") or {}
    floors = max(int(project_info.get("floors") or 1), 1)
    _resolve_quantity_predictor_items(computed, project_info, geo_conf=0.0, geometry=None, floors=floors)
    return computed


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _geometry_is_usable(geometry: dict | None) -> bool:
    """Return True only if the geometry dict contains at least one non-zero measurement."""
    if not geometry:
        return False
    return (
        float(geometry.get("total_floor_area_m2") or 0) > 0
        or float(geometry.get("wall_length_m") or 0) > 0
        or int(geometry.get("opening_count") or 0) > 0
    )


def _resolve_quantity_predictor_items(
    items_to_resolve: list[dict],
    project_info: dict,
    geo_conf: float = 0.0,
    geometry: dict | None = None,
    floors: int = 1,
) -> None:
    """Generate candidates and reconcile for items without a geometry candidate.

    For the no-floorplan path (Phase 5): runs parametric candidate generation
    and ML candidate generation in parallel, then reconciles the results.
    For the geometry path: ML-only path for items where no geometry rule applied.

    Lump-sum categories are assigned quantity = 1.0 (QS convention).
    """
    _LUMP_SUM = {"preliminary_and_general", "miscellaneous", "other", "testing_and_commissioning"}

    distribution_groups: dict[str, list[dict]] = {}

    for item in items_to_resolve:
        category = (item.get("category") or "misc").lower()
        item_unit = item.get("unit") or item.get("preferred_unit") or ""

        # ── Lump-sum convention ───────────────────────────────────────────
        if category in _LUMP_SUM:
            item["quantity"]                  = 1.0
            item["final_quantity"]            = 1.0
            item["quantity_source"]           = "rule_based"
            item["quantity_confidence_score"] = 1.0
            item["quantity_confidence"]       = 1.0
            item["quantity_candidates"]       = [{
                "candidate_type": "rule_based",
                "quantity": 1.0, "unit": item_unit, "confidence": 1.0,
                "assumptions": ["lump_sum_convention"], "method": "rule_based",
                "diagnostics": {}, "requires_review": False,
                "source_payload": {"source": "rule_based", "allocation_mode": "direct"},
            }]
            item["reconciliation_summary"] = {
                "method": "lump_sum",
                "source": "rule_based",
                "candidate_count": 1,
                "disagreement_score": 0.0,
                "review_flags": [],
            }
            continue

        # ── Phase 5: parametric candidate (no floorplan path) ──────────────
        candidates: list[tuple[float, str, bool]] = []
        param_qty, param_src = calculate_parametric(item, project_info)
        if param_qty is not None and param_qty > 0:
            candidates.append((param_qty, "parametric", False))

        # ── ML candidate ────────────────────────────────────────────────────
        ml_result = predict_quantity(item, project_info)
        ml_qty    = ml_result["quantity"]
        is_item_level = ml_result["is_item_level"]
        ml_diag   = ml_result

        if is_item_level and ml_qty > 0:
            item["_ml_direct"] = True
            candidates.append((ml_qty, "quantity_predictor", True))
            # Stage 2: reconcile directly
            fused_qty, conf, dominant_src, cands_meta = fuse_candidates(
                candidates, geo_conf, unit=item_unit, ml_diagnostics=ml_diag
            )
            item["quantity"]                  = fused_qty
            item["final_quantity"]            = fused_qty
            item["quantity_source"]           = dominant_src
            item["quantity_confidence_score"] = conf
            item["quantity_confidence"]       = conf
            item["quantity_candidates"]       = cands_meta
            item["reconciliation_summary"]    = _build_reconciliation_summary(
                cands_meta, fused_qty, dominant_src, item_unit
            )
            # Stage 3: validate
            validate_quantity(item, geometry, floors)
        else:
            # Global ML model → distribute category totals later
            item["_raw_cat_qty"]   = ml_qty
            item["_ml_diag"]       = ml_diag
            item["_candidates"]    = candidates   # may include parametric
            item["_item_unit"]     = item_unit
            cat = (item.get("category") or "misc").lower()
            if cat not in distribution_groups:
                distribution_groups[cat] = []
            distribution_groups[cat].append(item)

    # ── Distribute global ML predictions by QS weights ───────────────────────
    for category, group_items in distribution_groups.items():
        if not group_items:
            continue

        category_total_qty = group_items[0]["_raw_cat_qty"]
        if category_total_qty <= 0:
            continue

        weights = [_get_qs_weight(category, item.get("description", "")) for item in group_items]
        total_weight = sum(weights)

        for item, weight in zip(group_items, weights):
            item_unit     = item.pop("_item_unit", "")
            ml_diag       = item.pop("_ml_diag", {})
            pre_candidates = item.pop("_candidates", [])
            item.pop("_raw_cat_qty", None)
            item.pop("_ml_direct", None)

            if total_weight > 0:
                alloc_qty = round(category_total_qty * (weight / total_weight), 2)
            else:
                alloc_qty = round(category_total_qty / len(group_items), 2)

            # Mark as global_allocation
            ml_diag_copy = dict(ml_diag)
            ml_diag_copy["allocation_mode"] = "global_allocation"

            candidates = list(pre_candidates) + [(alloc_qty, "quantity_predictor", False)]
            fused_qty, conf, dominant_src, cands_meta = fuse_candidates(
                candidates, geo_conf, unit=item_unit, ml_diagnostics=ml_diag_copy
            )
            item["quantity"]                  = fused_qty
            item["final_quantity"]            = fused_qty
            item["quantity_source"]           = dominant_src
            item["quantity_confidence_score"] = conf
            item["quantity_confidence"]       = conf
            item["quantity_candidates"]       = cands_meta
            item["reconciliation_summary"]    = _build_reconciliation_summary(
                cands_meta, fused_qty, dominant_src, item_unit
            )
            # Stage 3: validate
            validate_quantity(item, geometry, floors)

    # Clean up temp keys
    for item in items_to_resolve:
        for k in ("_ml_direct", "_raw_cat_qty", "_ml_diag", "_candidates", "_item_unit"):
            item.pop(k, None)


def _get_qs_weight(category: str, description: str) -> float:
    """Determine a relative weight for an item within its category using QS heuristic rules."""
    desc = str(description).lower()

    QS_RULES = {
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
            ("plaster", 40.0), ("render", 35.0), ("skim", 30.0), ("wall", 40.0), ("internal", 30.0), ("external", 20.0),
        ],
        "painting_and_finishes": [
            ("paint", 30.0), ("emulsion", 25.0), ("primer", 20.0), ("enamel", 15.0), ("weathershield", 20.0),
            ("wax", 10.0), ("preserv", 10.0), ("woodwork", 15.0), ("steelwork", 10.0), ("grille", 10.0),
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

    rules = QS_RULES.get(category, [])
    for keyword, weight in rules:
        if keyword in desc:
            return weight

    return 10.0  # Default weight if no keywords match


# ---------------------------------------------------------------------------
# Phase 11: Reconciliation summary with disagreement score and review flags
# ---------------------------------------------------------------------------

# Disagreement threshold above which items are flagged for review
_DISAGREEMENT_REVIEW_THRESHOLD = 0.50


def _build_reconciliation_summary(
    cands_meta: list[dict],
    fused_qty: float,
    dominant_src: str,
    unit: str,
) -> dict:
    """Build a Phase 11 reconciliation summary with disagreement score and review flags.

    Parameters
    ----------
    cands_meta:
        Candidate metadata list from ``fuse_candidates``.
    fused_qty:
        The reconciled final quantity.
    dominant_src:
        The source label of the highest-weight candidate.
    unit:
        BOQ item unit string.

    Returns
    -------
    dict
        ``reconciliation_summary`` with keys:
          - ``method``            : "weighted_fusion" | "discrete_winner" | "lump_sum"
          - ``source``            : dominant source label
          - ``candidate_count``   : int
          - ``disagreement_score``: float 0–∞ (δ = (max−min)/q̄)
          - ``reconciliation_reason``: str
          - ``review_flags``      : list[str]
    """
    n = len(cands_meta)
    if n == 0:
        return {
            "method": "none",
            "source": dominant_src,
            "candidate_count": 0,
            "disagreement_score": 0.0,
            "reconciliation_reason": "no_candidates",
            "review_flags": ["no_candidates"],
        }

    # Compute disagreement score: δ = (max(q_i) − min(q_i)) / max(q̄, 1)
    qs = [c["quantity"] for c in cands_meta if c["quantity"] > 0]
    if len(qs) > 1:
        q_bar = sum(qs) / len(qs)
        delta = (max(qs) - min(qs)) / max(q_bar, 1.0)
    else:
        delta = 0.0

    # Determine reconciliation method
    has_discrete_winner = any(
        c.get("diagnostics", {}).get("discrete_winner")
        for c in cands_meta
    )
    if n == 1:
        method = "single_candidate"
        reason = f"only_{cands_meta[0]['candidate_type']}_available"
    elif has_discrete_winner:
        method = "discrete_winner"
        reason = f"discrete_unit_{unit}_winner_selection"
    else:
        method = "weighted_fusion"
        reason = f"{n}_candidates_weighted_fusion"

    # Build review flags
    review_flags: list[str] = []
    if delta >= _DISAGREEMENT_REVIEW_THRESHOLD:
        review_flags.append(f"high_disagreement_{delta:.2f}")

    # Flag if the winner is a low-confidence global-allocation result
    winner_is_global = dominant_src == "quantity_predictor" and not any(
        c["candidate_type"] == "ml_item_level" and c["method"] == dominant_src
        for c in cands_meta
    )
    if winner_is_global and n == 1:
        review_flags.append("global_allocation_only")

    # Flag any candidate marked requires_review
    if any(c.get("requires_review") for c in cands_meta):
        review_flags.append("candidate_requires_review")

    return {
        "method":               method,
        "source":               dominant_src,
        "candidate_count":      n,
        "disagreement_score":   round(delta, 4),
        "reconciliation_reason": reason,
        "review_flags":         review_flags,
    }

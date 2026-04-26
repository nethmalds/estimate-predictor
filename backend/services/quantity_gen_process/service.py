"""Quantity Take-Off Engine — branching compute logic.

Branch A (floorplan geometry available):
  1. Apply geometry/rule-based formulas for each BOQ item category.
  2. Collect items where no geometry rule applied.
  3. Call Quantity Predictor ONLY for those missing items.
  Tags: ``quantity_source`` = ``"geometry"`` | ``"rule_based"`` | ``"quantity_predictor"``

Branch B (no floorplan):
  Call Quantity Predictor for ALL items.
  Tags: ``quantity_source`` = ``"quantity_predictor"``
"""
from __future__ import annotations

from typing import Any

from services.quantity_gen_process.rule_based_calculator import calculate_from_geometry
from services.quantity_gen_process.quantity_calculator import predict_quantity
from core.logging.logger import get_logger

logger = get_logger(__name__)


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
        Each item enriched with ``quantity`` and ``quantity_source``.
    """
    parameters: dict = project_info.get("parameters") or {}
    floors: int = max(int(project_info.get("floors") or 1), 1)

    has_geometry = _geometry_is_usable(floorplan_geometry)

    if has_geometry:
        logger.info("qto_engine branch=floorplan items=%d", len(boq_items))
        return _compute_with_geometry(boq_items, project_info, floorplan_geometry, floors, parameters)

    logger.info("qto_engine branch=no_floorplan items=%d", len(boq_items))
    return _compute_quantity_predictor_all(boq_items, project_info)


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
    computed: list[dict] = []
    quantity_predictor_needed: list[dict] = []

    for item in boq_items:
        qty, source = calculate_from_geometry(
            item,
            geometry,
            floors=floors,
            parameters=parameters,
        )
        item_copy = dict(item)
        if qty is not None:
            item_copy["quantity"] = qty
            item_copy["quantity_source"] = source
            computed.append(item_copy)
        else:
            quantity_predictor_needed.append(item_copy)

    if quantity_predictor_needed:
        _resolve_quantity_predictor_items(quantity_predictor_needed, project_info)
        computed.extend(quantity_predictor_needed)

    geo_count = len(boq_items) - len(quantity_predictor_needed)
    logger.info(
        "qto_engine geometry_items=%d quantity_predictor_items=%d",
        geo_count,
        len(quantity_predictor_needed),
    )
    return computed


# ---------------------------------------------------------------------------
# Branch B — No floorplan
# ---------------------------------------------------------------------------

def _compute_quantity_predictor_all(
    boq_items: list[dict],
    project_info: dict,
) -> list[dict]:
    computed: list[dict] = [dict(item) for item in boq_items]
    _resolve_quantity_predictor_items(computed, project_info)
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


def _resolve_quantity_predictor_items(items_to_resolve: list[dict], project_info: dict) -> None:
    """Run quantity predictor on items, distributing category-level predictions by QS weights.

    Preliminaries and misc items are lump-sum by QS convention and are assigned
    quantity = 1.0 directly without passing through the ML model.
    """
    _LUMP_SUM_CATEGORIES = {"preliminaries", "misc"}

    distribution_groups: dict[str, list[dict]] = {}

    for item in items_to_resolve:
        category = (item.get("category") or "misc").lower()

        # ── Rule-based lump-sum items ────────────────────────────────────
        if category in _LUMP_SUM_CATEGORIES:
            item["quantity"] = 1.0
            item["quantity_source"] = "rule_based"
            continue

        # ── ML prediction ────────────────────────────────────────────────
        qty, source, is_item_level = predict_quantity(item, project_info)
        item["quantity_source"] = source
        if is_item_level:
            item["quantity"] = qty
        else:
            item["_raw_cat_qty"] = qty
            if category not in distribution_groups:
                distribution_groups[category] = []
            distribution_groups[category].append(item)

    # Distribute category-level ML predictions among items using QS weights
    for category, group_items in distribution_groups.items():
        if not group_items:
            continue

        category_total_qty = group_items[0]["_raw_cat_qty"]

        if category_total_qty <= 0:
            logger.warning(
                "qto_engine ML returned non-positive qty=%.4f for category=%s",
                category_total_qty,
                category,
            )

        weights = [_get_qs_weight(category, item.get("description", "")) for item in group_items]
        total_weight = sum(weights)

        for item, weight in zip(group_items, weights):
            if total_weight > 0:
                item["quantity"] = round(category_total_qty * (weight / total_weight), 2)
            else:
                item["quantity"] = round(category_total_qty / len(group_items), 2)
            del item["_raw_cat_qty"]


def _get_qs_weight(category: str, description: str) -> float:
    """Determine a relative weight for an item within its category using QS heuristic rules."""
    desc = str(description).lower()

    QS_RULES = {
        "structure": [
            ("slab", 40.0), ("beam", 25.0), ("column", 20.0), ("stair", 15.0),
            ("lintel", 5.0), ("reinforcement", 30.0), ("formwork", 30.0),
            ("grade 20", 35.0), ("grade 25", 35.0), ("concrete", 30.0),
            ("tor steel", 30.0), ("mild steel", 25.0), ("brc mesh", 20.0),
        ],
        "masonry": [
            ("9", 70.0), ("225", 70.0), ("4.5", 30.0), ("112", 30.0),
            ("brick", 50.0), ("block", 50.0),
        ],
        "finishes": [
            ("floor", 50.0), ("wall", 40.0), ("internal", 30.0), ("external", 20.0),
            ("ceiling", 10.0), ("soffit", 10.0), ("skirting", 10.0),
            ("plaster", 40.0), ("render", 35.0), ("skim", 30.0),
            ("paint", 30.0), ("tile", 50.0),
            ("wax", 10.0), ("preserv", 10.0), ("emulsion", 25.0),
            ("primer", 20.0), ("enamel", 15.0), ("weathershield", 20.0),
            ("woodwork", 15.0), ("steelwork", 10.0), ("grille", 10.0),
        ],
        "roof": [
            ("timber", 50.0), ("framework", 50.0), ("tile", 40.0), ("sheet", 40.0),
            ("ridge", 5.0), ("valance", 5.0), ("gutter", 5.0), ("downpipe", 5.0),
            ("asbestos", 40.0),
        ],
        "plumbing": [
            ("water closet", 20.0), ("wc", 20.0), ("pipe", 20.0), ("shower", 15.0),
            ("basin", 15.0), ("sink", 10.0), ("tank", 10.0), ("tap", 5.0),
            ("gully", 5.0),
        ],
        "electrical": [
            ("light", 30.0), ("socket", 25.0), ("cable", 15.0), ("wire", 15.0),
            ("switch", 10.0), ("fan", 10.0), ("distribution board", 5.0),
            ("db", 5.0), ("floodlight", 20.0), ("led", 15.0),
        ],
        "foundation": [
            ("excavat", 40.0), ("footing", 40.0), ("foundation", 40.0), ("rubble", 30.0),
            ("backfill", 30.0), ("earth", 30.0), ("concrete", 20.0), ("screed", 15.0),
            ("pcc", 15.0), ("sand", 15.0), ("river sand", 18.0),
            ("cement pot", 10.0),
        ],
        "site": [
            ("clear", 50.0), ("excavat", 50.0), ("trench", 40.0), ("transport", 20.0),
        ],
        "openings": [
            ("window", 40.0), ("casement", 40.0), ("glaz", 35.0), ("door", 35.0),
        ],
        "demolitions": [
            ("brick wall", 50.0), ('9" brick', 50.0), ("drain", 30.0),
            ("demolit", 40.0), ("remov", 30.0),
        ],
    }

    rules = QS_RULES.get(category, [])
    for keyword, weight in rules:
        if keyword in desc:
            return weight

    return 10.0  # Default weight if no keywords match

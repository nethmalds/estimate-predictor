"""Three-stage BOQ item generation.

Stage 1 — Real Item Predictor  → candidate items (Random Forest predictions)
Stage 2 — LLM Initial QS Pass  → baseline BOQ item list, seeded with predictor hints
Stage 3 — LLM Gap Fill         → compare baseline vs Item Predictor, add ONLY missing items

Each item in the final list is tagged with a ``source`` field:
  ``"llm_baseline"``  — came from the LLM initial QS pass
  ``"item_predictor"``— added because Item Predictor predicted it and LLM confirmed it missing
  ``"llm_reconciled"``  — part of the final reconciled BOQ returned by Stage 3
"""
from __future__ import annotations

import difflib
import re
from typing import Any, Callable

from services.item_gen_process.item_predictor import predict_boq_items, predict_boq_items_with_confidence
from services.item_gen_process.llm_client import (
    generate_baseline_boq,
    gap_fill_boq_items,
)



_CATEGORY_RULES: list[tuple[str, str, str]] = [
    (r"\b(brick|block|masonry|wall)\b", "brick_masonry", "Brick Masonry"),
    (r"\b(concrete|rcc|screed|mass concrete|grade \d+)\b", "concrete_works", "Concrete Works"),
    (r"\b(demolish|dismantle|remove|clearing away)\b", "demolition_and_removal", "Demolition & Removal"),
    (r"\b(door|window|hinge|lock|frame|glass|glazing)\b", "doors_windows_and_glazing", "Doors, Windows & Glazing"),
    (r"\b(light|switch|socket|fan|wire|cable|conduit|electrical|ac|air condition|mechanical)\b", "electrical_and_mechanical", "Electrical & Mechanical"),
    (r"\b(site|clearing|top soil|excavation|earthwork|trench|backfill)\b", "excavation_and_earthwork", "Excavation & Earthwork"),
    (r"\b(paving|landscaping|external|road|fence|gate)\b", "external_and_civil_works", "External & Civil Works"),
    (r"\b(tile|flooring|skirting|terrazzo|timber floor)\b", "flooring_and_tiling", "Flooring & Tiling"),
    (r"\b(shuttering|formwork|mould)\b", "formwork", "Formwork"),
    (r"\b(paint|primer|emulsion|enamel|varnish|decorat)\b", "painting_and_finishes", "Painting & Finishes"),
    (r"\b(pile|piling|substructure|foundation|plinth|footing|dpc|pcc)\b", "piling_and_substructure", "Piling & Substructure"),
    (r"\b(plaster|render|skim coat|putty)\b", "plastering_and_rendering", "Plastering & Rendering"),
    (r"\b(security|advance payment|preliminary|preliminaries|general)\b", "preliminary_and_general", "Preliminary & General"),
    (r"\b(reinforcement|rebar|mesh|tor steel|mild steel)\b", "reinforcement", "Reinforcement"),
    (r"\b(roof|asbestos|gutter|down pipe|flashing|ridge|valance|barge|ceiling|waterproof)\b", "roofing_and_ceiling", "Roofing & Ceiling"),
    (r"\b(tap|waste|pipe|water closet|bidet|soap|toilet|basin|plumbing|sanitary|drainage)\b", "sanitary_and_plumbing", "Sanitary & Plumbing"),
    (r"\b(test|commission|inspect)\b", "testing_and_commissioning", "Testing & Commissioning"),
]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

ProgressCallback = Callable[[str, str, dict | None], None]

# Fuzzy dedup threshold (Q-C): items with similarity ≥ this value are merged.
_DEDUP_SIMILARITY_THRESHOLD = 0.90


class EstimationError(RuntimeError):
    """Raised when the BOQ generation pipeline produces no usable items."""


def build_final_boq_items(
    project_info: dict,
    floorplan_geometry: dict | None = None,
    progress_callback: ProgressCallback | None = None,
) -> list[dict[str, Any]]:
    """Execute the three-stage BOQ generation and return a fully tagged item list.

    Parameters
    ----------
    project_info:
        Normalised project info dict from the clarification pipeline.
    floorplan_geometry:
        Optional geometry dict from the CV pipeline (used for future enrichment).
    progress_callback:
        Optional callback to emit progress events to the frontend.

    Returns
    -------
    list[dict]
        Each dict has keys: description, category, section, source, floors.
    """
    floors = project_info.get("floors") or 1

    # -----------------------------------------------------------------------
    # Stage 1: Item Predictor → candidate items (runs first to seed Stage 2)
    # -----------------------------------------------------------------------
    item_predictor_with_conf: list[dict] = []
    try:
        item_predictor_with_conf = predict_boq_items_with_confidence(project_info)
        item_predictor_raw = [entry["description"] for entry in item_predictor_with_conf]
    except Exception:
        item_predictor_raw = []

    # Build a lookup from description → source_confidence for enrichment later
    _predictor_conf: dict[str, float] = {
        e["description"]: e["source_confidence"]
        for e in item_predictor_with_conf
    }

    # -----------------------------------------------------------------------
    # Stage 2: LLM Initial QS Pass → baseline BOQ, seeded with predictor hints
    # -----------------------------------------------------------------------
    try:
        baseline_items = generate_baseline_boq(project_info, item_predictor_hints=item_predictor_raw)
    except Exception:
        baseline_items = []

    for item in baseline_items:
        item["source"] = "llm_baseline"

    # -----------------------------------------------------------------------
    # Stage 3: LLM Full Reconciliation — returns the COMPLETE final BOQ list
    # -----------------------------------------------------------------------
    reconciled_items: list[dict] = []
    try:
        reconciled_items = gap_fill_boq_items(project_info, baseline_items, item_predictor_raw)
    except Exception:
        reconciled_items = baseline_items

    for item in reconciled_items:
        if not item.get("source"):
            item["source"] = "llm_reconciled"

    # -----------------------------------------------------------------------
    # Deduplicate as safety fallback (C5)
    # -----------------------------------------------------------------------
    deduped, removed_count = _deduplicate_items(reconciled_items)
    if removed_count:
        if progress_callback:
            progress_callback(
                "item_deduplication",
                "completed",
                {"removed_duplicates": removed_count, "remaining_items": len(deduped)},
            )

    final_items: list[dict[str, Any]] = []
    for item in deduped:
        enriched = _enrich_item(item, floors, _predictor_conf)
        final_items.append(enriched)

    # C6: empty BOQ is a hard failure
    if not final_items:
        raise EstimationError(
            "BOQ generation produced no items. All three stages (Item Predictor, "
            "LLM Baseline, Reconciliation) failed or returned empty results."
        )

    return final_items


# ---------------------------------------------------------------------------
# BOQ item contract metadata tables (Phase 2)
# ---------------------------------------------------------------------------

# Category slug → ML Work_Category label (matches quantity_calculator training)
_CATEGORY_TO_WORK_CATEGORY: dict[str, str] = {
    "structure":                "Concrete Works",
    "concrete_works":           "Concrete Works",
    "foundation":               "Piling & Substructure",
    "piling_and_substructure":  "Piling & Substructure",
    "masonry":                  "Brick Masonry",
    "brick_masonry":            "Brick Masonry",
    "finishes":                 "Plastering & Rendering",
    "plastering_and_rendering": "Plastering & Rendering",
    "painting_and_finishes":    "Painting & Finishes",
    "roof":                     "Roofing & Ceiling",
    "roofing_and_ceiling":      "Roofing & Ceiling",
    "openings":                 "Doors, Windows & Glazing",
    "doors_windows_and_glazing":"Doors, Windows & Glazing",
    "electrical":               "Electrical & Mechanical",
    "electrical_and_mechanical":"Electrical & Mechanical",
    "plumbing":                 "Sanitary & Plumbing",
    "sanitary_and_plumbing":    "Sanitary & Plumbing",
    "site":                     "Excavation & Earthwork",
    "excavation_and_earthwork": "Excavation & Earthwork",
    "external":                 "External & Civil Works",
    "external_and_civil_works": "External & Civil Works",
    "demolitions":              "Demolition & Removal",
    "demolition_and_removal":   "Demolition & Removal",
    "preliminaries":            "Preliminary & General",
    "preliminary_and_general":  "Preliminary & General",
    "formwork":                 "Formwork",
    "reinforcement":            "Reinforcement",
    "flooring_and_tiling":      "Flooring & Tiling",
    "testing_and_commissioning":"Testing & Commissioning",
    "misc":                     "Miscellaneous",
    "miscellaneous":            "Miscellaneous",
}

# Category slug → default unit
_CATEGORY_TO_UNIT: dict[str, str] = {
    "concrete_works":           "m³",
    "piling_and_substructure":  "m³",
    "brick_masonry":            "m²",
    "plastering_and_rendering": "m²",
    "painting_and_finishes":    "m²",
    "roofing_and_ceiling":      "m²",
    "doors_windows_and_glazing":"Nr",
    "electrical_and_mechanical":"Nr",
    "sanitary_and_plumbing":    "Nr",
    "excavation_and_earthwork": "m³",
    "external_and_civil_works": "m²",
    "demolition_and_removal":   "m²",
    "preliminary_and_general":  "Item",
    "formwork":                 "m²",
    "reinforcement":            "Kg",
    "flooring_and_tiling":      "m²",
    "testing_and_commissioning":"Item",
    "miscellaneous":            "Item",
}

# Category slug → material type (matches quantity_calculator training)
_CATEGORY_TO_MATERIAL_TYPE: dict[str, str] = {
    "concrete_works":           "Concrete",
    "piling_and_substructure":  "Concrete",
    "brick_masonry":            "Masonry",
    "plastering_and_rendering": "Masonry",
    "painting_and_finishes":    "Paint/Chemical",
    "roofing_and_ceiling":      "Ceiling/Roofing Sheet",
    "doors_windows_and_glazing":"Aluminium/Glass",
    "electrical_and_mechanical":"Electrical",
    "sanitary_and_plumbing":    "Sanitary Ware",
    "excavation_and_earthwork": "Earthwork/Aggregate",
    "external_and_civil_works": "Paving",
    "demolition_and_removal":   "General",
    "preliminary_and_general":  "General",
    "formwork":                 "Timber",
    "reinforcement":            "Steel/Metal",
    "flooring_and_tiling":      "Tiles",
    "testing_and_commissioning":"General",
    "miscellaneous":            "General",
}

# Units classified as discrete (counted items — Phase 10)
_DISCRETE_UNITS: frozenset[str] = frozenset({
    "nr", "nr.", "no", "no.", "item", "pair", "set", "each", "lot",
})


def _classify_unit_kind(unit: str) -> str:
    """Return ``"discrete"`` or ``"continuous"`` based on the unit string."""
    return "discrete" if unit.strip().lower() in _DISCRETE_UNITS else "continuous"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _enrich_item(item: dict[str, Any], floors: int, predictor_conf: dict[str, float] | None = None) -> dict[str, Any]:
    """Ensure category/section are set and attach floors + Phase 2 metadata."""
    enriched = dict(item)
    description = enriched.get("description") or ""

    if not enriched.get("category") or enriched.get("category") in ("misc", "miscellaneous", "other"):
        enriched["category"] = _infer_category(description)
    if not enriched.get("section") or enriched.get("section") in ("Miscellaneous", "Other"):
        enriched["section"] = _infer_section(description)

    enriched["floors"] = floors

    # Phase 2: stable BOQ item contract metadata
    cat = (enriched.get("category") or "misc").lower()
    preferred_unit = _CATEGORY_TO_UNIT.get(cat, "Item")

    if not enriched.get("work_category"):
        enriched["work_category"] = _CATEGORY_TO_WORK_CATEGORY.get(cat, "Miscellaneous")
    if not enriched.get("material_type"):
        enriched["material_type"] = _CATEGORY_TO_MATERIAL_TYPE.get(cat, "General")
    if not enriched.get("preferred_unit"):
        enriched["preferred_unit"] = preferred_unit
    if not enriched.get("unit_kind"):
        enriched["unit_kind"] = _classify_unit_kind(preferred_unit)

    # Preserve Item Predictor confidence (source_confidence)
    if not enriched.get("source_confidence"):
        if predictor_conf and description in predictor_conf:
            enriched["source_confidence"] = predictor_conf[description]
        elif enriched.get("source") == "item_predictor":
            enriched["source_confidence"] = 0.70   # default when confidence unknown
        else:
            enriched["source_confidence"] = 0.60   # LLM-generated item baseline confidence

    return enriched


def _deduplicate_items(
    items: list[dict[str, Any]],
    threshold: float = _DEDUP_SIMILARITY_THRESHOLD,
) -> tuple[list[dict[str, Any]], int]:
    """Remove near-duplicate BOQ items using fuzzy string matching (C5).

    Two items are considered duplicates when the similarity ratio of their
    normalised descriptions is ≥ *threshold* (default 0.90 = 90%).
    The first occurrence is kept; subsequent duplicates are dropped.

    Returns
    -------
    (deduped_list, removed_count)
    """
    unique: list[dict[str, Any]] = []
    removed = 0
    for candidate in items:
        norm_cand = _norm_desc(candidate.get("description") or "")
        is_dup = False
        for kept in unique:
            ratio = difflib.SequenceMatcher(
                None,
                norm_cand,
                _norm_desc(kept.get("description") or ""),
            ).ratio()
            if ratio >= threshold:
                is_dup = True
                break
        if not is_dup:
            unique.append(candidate)
        else:
            removed += 1
    return unique, removed


def _norm_desc(text: str) -> str:
    """Lowercase and strip punctuation for fuzzy comparison."""
    return re.sub(r"[^a-z0-9 ]", "", text.lower()).strip()


def _infer_category(description: str) -> str:
    for pattern, category, _section in _CATEGORY_RULES:
        if re.search(pattern, description, re.IGNORECASE):
            return category
    return "miscellaneous"


def _infer_section(description: str) -> str:
    for pattern, _category, section in _CATEGORY_RULES:
        if re.search(pattern, description, re.IGNORECASE):
            return section
    return "Miscellaneous"

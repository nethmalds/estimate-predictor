"""Three-stage BOQ item generation.

Stage 1 — Real Item Predictor  → candidate items (Random Forest predictions)
Stage 2 — LLM Initial QS Pass  → baseline BOQ item list, seeded with predictor hints
Stage 3 — LLM Gap Fill         → compare baseline vs Item Predictor, add ONLY missing items

Each item in the final list is tagged with a ``source`` field:
  ``"llm_baseline"``  — came from the LLM initial QS pass
  ``"item_predictor"``— added because Item Predictor predicted it and LLM confirmed it missing
  ``"llm_gap_fill"``  — explicitly added during the LLM gap-fill comparison step
"""
from __future__ import annotations

import difflib
import re
from typing import Any, Callable

from services.item_gen_process.item_predictor import predict_boq_items
from services.item_gen_process.llm_client import (
    generate_baseline_boq,
    gap_fill_boq_items,
)
from core.logging.logger import get_logger, log_payload

logger = get_logger(__name__)


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
    logger.info("boq_stage1_item_predictor start")
    try:
        item_predictor_raw: list[str] = predict_boq_items(project_info)
    except Exception:
        logger.exception("boq_stage1_item_predictor failed — using empty predictions")
        item_predictor_raw = []
    logger.info("boq_stage1_item_predictor predictions=%d", len(item_predictor_raw))
    log_payload("item_predictor_raw", item_predictor_raw)

    # -----------------------------------------------------------------------
    # Stage 2: LLM Initial QS Pass → baseline BOQ, seeded with predictor hints
    # -----------------------------------------------------------------------
    logger.info("boq_stage2_baseline_boq start")
    try:
        baseline_items = generate_baseline_boq(project_info, item_predictor_hints=item_predictor_raw)
    except Exception:
        logger.exception("boq_stage2_baseline_boq failed — using empty baseline")
        baseline_items = []

    for item in baseline_items:
        item["source"] = "llm_baseline"
    logger.info("boq_stage2_baseline_boq items=%d", len(baseline_items))
    log_payload("llm_baseline_boq", baseline_items)

    # -----------------------------------------------------------------------
    # Stage 3: LLM Gap Fill → compare & add only missing relevant items
    # -----------------------------------------------------------------------
    logger.info("boq_stage3_gap_fill start")
    added_items: list[dict] = []
    try:
        added_items = gap_fill_boq_items(project_info, baseline_items, item_predictor_raw)
    except Exception:
        logger.exception("boq_stage3_gap_fill failed — skipping gap fill")

    for item in added_items:
        item["source"] = "llm_gap_fill"
    logger.info("boq_stage3_gap_fill added=%d", len(added_items))
    log_payload("llm_gap_fill_additions", added_items)

    # -----------------------------------------------------------------------
    # Merge and deduplicate (C5)
    # -----------------------------------------------------------------------
    merged: list[dict[str, Any]] = baseline_items + added_items
    deduped, removed_count = _deduplicate_items(merged)
    if removed_count:
        logger.warning("boq_dedup removed=%d (similarity≥%.0f%%)", removed_count, _DEDUP_SIMILARITY_THRESHOLD * 100)

    final_items: list[dict[str, Any]] = []
    for item in deduped:
        enriched = _enrich_item(item, floors)
        final_items.append(enriched)

    # C6: empty BOQ is a hard failure
    if not final_items:
        raise EstimationError(
            "BOQ generation produced no items. All three stages (Item Predictor, "
            "LLM Baseline, Gap Fill) failed or returned empty results."
        )

    logger.info("boq_final items=%d (deduped=%d removed)", len(final_items), removed_count)
    log_payload("final_boq_items_merged", final_items)
    return final_items


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _enrich_item(item: dict[str, Any], floors: int) -> dict[str, Any]:
    """Ensure category/section are set and attach floors metadata."""
    enriched = dict(item)
    description = enriched.get("description") or ""

    if not enriched.get("category") or enriched.get("category") in ("misc", "miscellaneous", "other"):
        enriched["category"] = _infer_category(description)
    if not enriched.get("section") or enriched.get("section") in ("Miscellaneous", "Other"):
        enriched["section"] = _infer_section(description)

    enriched["floors"] = floors
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
                logger.warning(
                    "boq_dedup_item desc=%r matches=%r similarity=%.3f",
                    candidate.get("description"),
                    kept.get("description"),
                    ratio,
                )
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

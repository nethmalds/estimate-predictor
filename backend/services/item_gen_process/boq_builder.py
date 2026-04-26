"""Three-stage BOQ item generation.

Stage 1 — LLM Initial QS Pass  → baseline BOQ item list
Stage 2 — Real Item Predictor          → additional candidate items (Random Forest predictions)
Stage 3 — LLM Gap Fill          → compare baseline vs Item Predictor, add ONLY missing items

Each item in the final list is tagged with a ``source`` field:
  ``"llm_baseline"``  — came from the LLM initial QS pass
  ``"item_predictor"``       — added because Item Predictor predicted it and LLM confirmed it missing
  ``"llm_gap_fill"``  — explicitly added during the LLM gap-fill comparison step
"""
from __future__ import annotations

import re
from typing import Any

from services.item_gen_process.item_predictor import predict_boq_items
from services.clarification_process.llm_client import (
    generate_baseline_boq,
    gap_fill_boq_items,
)
from core.logging.logger import get_logger

logger = get_logger(__name__)


_CATEGORY_RULES: list[tuple[str, str, str]] = [
    (r"\b(site|clearing|top soil|excavation|transport)\b", "site", "Site Works"),
    (r"\b(foundation|plinth|footing|dpc|pcc|anti-termite)\b", "foundation", "Substructure"),
    (r"\b(shuttering|formwork|column|beam|slab|reinforcement|rcc|concrete)\b", "structure", "Structure"),
    (r"\b(brick|block|masonry|partition|wall)\b", "masonry", "Masonry"),
    (r"\b(plaster|skirting|painting|primer|emulsion|finish)\b", "finishes", "Finishes"),
    (r"\b(roof|asbestos|gutter|down pipe|flashing|ridge|valance|barge)\b", "roof", "Roofing"),
    (r"\b(door|window|hinge|lock|frame)\b", "openings", "Openings"),
    (r"\b(light|switch|socket|fan|wire|cable|conduit|electrical)\b", "electrical", "Electrical"),
    (r"\b(tap|waste|pipe|water closet|bidet|soap|toilet|basin|plumbing)\b", "plumbing", "Plumbing"),
    (r"\b(security|advance payment|preliminary|preliminaries)\b", "preliminaries", "Preliminaries"),
    (r"\b(staircase)\b", "structure", "Structure"),
    (r"\b(waterproof)\b", "roof", "Roofing"),
]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_final_boq_items(
    project_info: dict,
    floorplan_geometry: dict | None = None,
) -> list[dict[str, Any]]:
    """Execute the three-stage BOQ generation and return a fully tagged item list.

    Parameters
    ----------
    project_info:
        Normalised project info dict from the clarification pipeline.
    floorplan_geometry:
        Optional geometry dict from the CV pipeline (used for future enrichment).

    Returns
    -------
    list[dict]
        Each dict has keys: description, category, section, source, floors.
    """
    floors = project_info.get("floors") or 1

    # -----------------------------------------------------------------------
    # Stage 1: LLM Initial QS Pass → baseline BOQ
    # -----------------------------------------------------------------------
    logger.info("boq_stage1_baseline_boq start")
    try:
        baseline_items = generate_baseline_boq(project_info)
    except Exception:
        logger.exception("boq_stage1_baseline_boq failed — using empty baseline")
        baseline_items = []

    for item in baseline_items:
        item["source"] = "llm_baseline"
    logger.info("boq_stage1_baseline_boq items=%d", len(baseline_items))

    # -----------------------------------------------------------------------
    # Stage 2: Item Predictor → additional candidate items
    # -----------------------------------------------------------------------
    logger.info("boq_stage2_item_predictor start")
    try:
        item_predictor_raw: list[str] = predict_boq_items(project_info)
    except Exception:
        logger.exception("boq_stage2_item_predictor failed — using empty predictions")
        item_predictor_raw = []
    logger.info("boq_stage2_item_predictor predictions=%d", len(item_predictor_raw))

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

    # -----------------------------------------------------------------------
    # Merge into final list
    # -----------------------------------------------------------------------
    final_items: list[dict[str, Any]] = []
    for item in baseline_items + added_items:
        enriched = _enrich_item(item, floors)
        final_items.append(enriched)

    logger.info("boq_final items=%d", len(final_items))
    return final_items


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _enrich_item(item: dict[str, Any], floors: int) -> dict[str, Any]:
    """Ensure category/section are set and attach floors metadata."""
    enriched = dict(item)
    description = enriched.get("description") or ""

    if not enriched.get("category") or enriched.get("category") == "misc":
        enriched["category"] = _infer_category(description)
    if not enriched.get("section") or enriched.get("section") == "Miscellaneous":
        enriched["section"] = _infer_section(description)

    enriched["floors"] = floors
    return enriched


def _infer_category(description: str) -> str:
    for pattern, category, _section in _CATEGORY_RULES:
        if re.search(pattern, description, re.IGNORECASE):
            return category
    return "misc"


def _infer_section(description: str) -> str:
    for pattern, _category, section in _CATEGORY_RULES:
        if re.search(pattern, description, re.IGNORECASE):
            return section
    return "Miscellaneous"

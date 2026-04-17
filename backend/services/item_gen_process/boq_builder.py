import re
from typing import Any

from services.item_gen_process.model_a_stub import get_sample_model_a_predictions
from services.clarification_process.llm_client import refine_boq_items as llm_refine_boq_items


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
]


def build_boq_items(project_info: dict, floorplan_summary: dict | None = None) -> list[dict[str, Any]]:
    floors = project_info.get("floors") or 1
    raw_predictions = get_sample_model_a_predictions()
    raw_items = [_normalize_prediction(item) for item in raw_predictions]

    refined_items = _refine_items(project_info, raw_items)

    for item in refined_items:
        item["floors"] = floors
        item["source"] = "model_a_stub"
        if floorplan_summary:
            item["floorplan"] = floorplan_summary.get("note")

    return refined_items


def _normalize_prediction(description: str) -> dict[str, Any]:
    clean_description, bsr_ref = _split_bsr_reference(description)
    return {
        "description": clean_description,
        "raw_description": description,
        "predicted_bsr_ref": bsr_ref,
    }


def _split_bsr_reference(description: str) -> tuple[str, str | None]:
    match = re.search(r"\(\s*bsr\s+([a-z0-9.]+)[^)]*\)", description, re.IGNORECASE)
    bsr_ref = match.group(1).lower() if match else None
    cleaned = re.sub(r"\s*\(\s*bsr[^)]*\)\s*", "", description, flags=re.IGNORECASE).strip()
    return cleaned, bsr_ref


def _refine_items(project_info: dict, raw_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    try:
        llm_items = llm_refine_boq_items(project_info, raw_items)
    except Exception:
        llm_items = []

    if llm_items:
        return _merge_refined_items(raw_items, llm_items)
    return [_apply_rules(item) for item in raw_items]


def _merge_refined_items(
    raw_items: list[dict[str, Any]],
    refined_items: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    for index, raw_item in enumerate(raw_items):
        refined_item = refined_items[index] if index < len(refined_items) else None
        if not refined_item:
            merged.append(_apply_rules(raw_item))
            continue
        merged_item = dict(raw_item)
        merged_item["description"] = refined_item.get("description") or raw_item.get("description")
        merged_item["category"] = refined_item.get("category") or _infer_category(raw_item.get("description"))
        merged_item["section"] = refined_item.get("section") or _infer_section(raw_item.get("description"))
        merged.append(merged_item)
    return merged


def _apply_rules(item: dict[str, Any]) -> dict[str, Any]:
    enriched = dict(item)
    description = item.get("description") or ""
    enriched["category"] = _infer_category(description)
    enriched["section"] = _infer_section(description)
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

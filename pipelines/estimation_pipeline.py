from ai.llm.clarification_agent import (
    build_clarification_questions,
    find_missing_fields,
    merge_parameters,
)
from ai.llm.llm_client import extract_project_info
from ai.rag.service import service as rag_service
from domain.assumptions.assumption_manager import build_assumptions
from domain.boq_generation.boq_builder import build_boq_items
from domain.pricing_engine.cost_calculator import calculate_costs
from domain.quantity_takeoff.service import compute_quantities
from domain.reporting.report_builder import build_report
from domain.validation.confidence_scoring import score_confidence
from domain.validation.quantity_validator import validate_quantities
from orchestration.floorplan_workflow import run_floorplan_workflow


def run_estimation_pipeline(
    description: str,
    floorplan_image_path: str | None = None,
    provided_parameters: dict | None = None,
) -> dict:
    project_info = extract_project_info(description)
    project_info = merge_parameters(project_info, provided_parameters)

    missing_fields = find_missing_fields(project_info)
    if missing_fields:
        return {
            "status": "needs_clarification",
            "missing_fields": missing_fields,
            "questions": build_clarification_questions(missing_fields),
            "project_info": project_info,
        }

    floorplan_summary = None
    if floorplan_image_path:
        floorplan_summary = run_floorplan_workflow(floorplan_image_path)

    boq_items = build_boq_items(project_info, floorplan_summary)
    quantities = compute_quantities(boq_items, project_info, floorplan_summary)
    matched_items = _match_bsr_items(quantities)
    validation = validate_quantities(matched_items)
    costs = calculate_costs(matched_items)
    assumptions = build_assumptions(project_info, floorplan_summary)
    confidence = score_confidence(project_info, floorplan_summary, validation.get("warnings"))

    payload = {
        "status": "estimated",
        "project_info": project_info,
        "floorplan": floorplan_summary,
        "boq_items": matched_items,
        "validation": validation,
        "costs": costs,
        "assumptions": assumptions,
        "confidence": confidence,
        "sources": _build_sources(project_info, floorplan_summary),
    }
    payload["report"] = build_report(payload)
    return payload


def _match_bsr_items(items: list[dict]) -> list[dict]:
    matched: list[dict] = []
    for item in items:
        description = item.get("description") or ""
        bsr_match = rag_service.match_boq_item(description)
        merged = dict(item)
        merged.update(
            {
                "bsr_item_no": bsr_match.get("item_no"),
                "bsr_description": bsr_match.get("description"),
                "unit": bsr_match.get("unit"),
                "rate": bsr_match.get("rate") or 0.0,
                "match_confidence": bsr_match.get("confidence"),
            }
        )
        matched.append(merged)
    return matched


def _build_sources(project_info: dict, floorplan_summary: dict | None) -> list[str]:
    sources = ["ollama_llm", "bsr_rag"]
    if floorplan_summary:
        sources.append("cv_ocr")
    if project_info.get("parameters"):
        sources.append("user_inputs")
    return sources

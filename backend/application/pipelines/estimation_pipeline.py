import time
from contextlib import contextmanager
from typing import Callable, Iterator

from services.clarification_process.clarification_agent import (
    build_clarification_questions,
    find_missing_fields,
)
from services.clarification_process.llm_client import check_requirements, extract_project_info
from services.rag_process.service import service as rag_service
from services.item_gen_process.boq_builder import build_boq_items
from services.pricing_process.cost_calculator import calculate_costs
from services.quantity_gen_process.service import compute_quantities
from services.reporting_process.report_builder import build_report
from services.validation.confidence_scoring import score_confidence
from services.validation.quantity_validator import validate_quantities
from core.logging.logger import get_logger


logger = get_logger(__name__)


ProgressCallback = Callable[[str, str, dict | None], None]


def run_estimation_pipeline(
    description: str,
    floorplan_image_url: str | None = None,
    progress_callback: ProgressCallback | None = None,
) -> dict:
    _emit_progress(progress_callback, "extract_project_info", "started", None)
    with _log_step("extract_project_info"):
        project_info = extract_project_info(description)
    _emit_progress(progress_callback, "extract_project_info", "completed", None)
    _emit_progress(progress_callback, "check_requirements", "started", None)
    with _log_step("check_requirements"):
        requirements_check = check_requirements(description)
    _emit_progress(progress_callback, "check_requirements", "completed", None)
    missing_fields = requirements_check.get("missing_fields") or []
    if not missing_fields:
        _emit_progress(progress_callback, "find_missing_fields", "started", None)
        with _log_step("find_missing_fields"):
            missing_fields = find_missing_fields(project_info)
        _emit_progress(progress_callback, "find_missing_fields", "completed", None)
    _emit_progress(progress_callback, "build_clarification_questions", "started", None)
    with _log_step("build_clarification_questions"):
        questions = requirements_check.get("questions") or build_clarification_questions(missing_fields)
    _emit_progress(progress_callback, "build_clarification_questions", "completed", None)
    if missing_fields:
        return {
            "status": "needs_clarification",
            "question": questions[0],
        }
    return run_estimation_pipeline_from_project_info(
        project_info,
        floorplan_image_url=floorplan_image_url,
        progress_callback=progress_callback,
    )


def run_estimation_pipeline_from_project_info(
    project_info: dict,
    floorplan_image_url: str | None = None,
    progress_callback: ProgressCallback | None = None,
) -> dict:
    floorplan_summary = None
    if floorplan_image_url:
        _emit_progress(progress_callback, "floorplan_skipped", "started", None)
        with _log_step("floorplan_skipped"):
            floorplan_summary = {
                "status": "ignored",
                "note": "Floorplan processing is disabled in this workflow.",
            }
        _emit_progress(progress_callback, "floorplan_skipped", "completed", floorplan_summary)

    _emit_progress(progress_callback, "model_a_predictions", "started", None)
    with _log_step("model_a_predictions"):
        boq_items = build_boq_items(project_info, floorplan_summary)
    _emit_progress(
        progress_callback,
        "model_a_predictions",
        "completed",
        {"item_count": len(boq_items), "items": boq_items},
    )

    _emit_progress(progress_callback, "model_b_quantities", "started", {"item_count": len(boq_items)})
    with _log_step("model_b_quantities", {"item_count": len(boq_items)}):
        quantities = compute_quantities(boq_items, project_info, floorplan_summary)
    _emit_progress(
        progress_callback,
        "model_b_quantities",
        "completed",
        {"item_count": len(quantities)},
    )

    _emit_progress(progress_callback, "bsr_matching", "started", {"item_count": len(quantities)})
    with _log_step("bsr_matching", {"item_count": len(quantities)}):
        matched_items = _match_bsr_items(quantities)

    payload = {
        "status": "draft_boq",
        "project_info": project_info,
        "floorplan": floorplan_summary,
        "boq_items": matched_items,
    }
    _emit_progress(
        progress_callback,
        "bsr_matching",
        "completed",
        payload,
    )
    return payload


def _emit_progress(
    callback: ProgressCallback | None,
    step: str,
    status: str,
    data: dict | None,
) -> None:
    if not callback:
        return
    callback(step, status, data)


@contextmanager
def _log_step(step: str, metadata: dict | None = None) -> Iterator[None]:
    start_time = time.perf_counter()
    logger.info("step_start step=%s metadata=%s", step, metadata or {})
    try:
        yield
        logger.info("step_ok step=%s", step)
    except Exception:  # noqa: BLE001 - preserve error context
        logger.exception("step_error step=%s", step)
        raise
    finally:
        duration_ms = (time.perf_counter() - start_time) * 1000.0
        logger.info("step_end step=%s duration_ms=%s", step, round(duration_ms, 2))


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
    sources = ["ollama_llm", "model_a_stub", "model_b_stub", "bsr_rag"]
    if floorplan_summary:
        sources.append("floorplan_disabled")
    if project_info.get("parameters"):
        sources.append("user_inputs")
    return sources

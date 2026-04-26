"""Estimation pipeline — orchestrates the full 11-stage estimation flow.

Stage sequence
--------------
1.  [Optional] Download & cache floorplan image          (floorplan_download)
2.  [Optional] CV pipeline → structured geometry          (floorplan_cv)
3.  LLM Initial QS Pass → baseline BOQ                   (baseline_boq)
4.  Real Item Predictor → additional candidate items             (item_predictor_predictions)
5.  LLM Gap Fill → final BOQ item list                   (gap_fill)
6.  RAG System → BSR codes / units / rates               (bsr_matching)
7.  Quantity Take-Off Engine (branched)                   (quantity_takeoff)
8.  Validation Layer (ranges + anomalies)                 (validation)
9.  Cost Calculation Engine (qty × rate)                  (cost_calculation)
10. Transparency & Confidence Layer                       (transparency)
11. Reporting Module                                      (reporting)
"""
from __future__ import annotations

import time
from contextlib import contextmanager
from typing import Callable, Iterator

from services.clarification_process.clarification_agent import (
    build_clarification_questions,
    find_missing_fields,
)
from services.clarification_process.llm_client import check_requirements, extract_project_info
from services.floorplan_process.image_cache import download_and_cache
from services.floorplan_process.pipeline import run_floorplan_pipeline
from services.item_gen_process.boq_builder import build_final_boq_items
from services.rag_process.service import service as rag_service
from services.quantity_gen_process.service import compute_quantities
from services.pricing_process.cost_calculator import calculate_costs
from services.reporting_process.report_builder import build_report
from services.validation.confidence_scoring import score_confidence
from services.validation.quantity_validator import validate_quantities
from core.logging.logger import get_logger

logger = get_logger(__name__)

import os
import pprint
from typing import Any

def _dev_log(step_name: str, output: Any, cb: ProgressCallback | None = None) -> Any:
    if os.getenv("ENV", "development") == "development":
        print(f"\n========== [DEV LOG] {step_name} Output ==========")
        pprint.pprint(output, indent=2, width=120)
        print("==================================================\n")
        if cb:
            cb(step_name, "dev_log", {"output": output})
    return output



ProgressCallback = Callable[[str, str, dict | None], None]


# ---------------------------------------------------------------------------
# Public entry points
# ---------------------------------------------------------------------------

def run_estimation_pipeline(
    description: str,
    floorplan_image_url: str | None = None,
    progress_callback: ProgressCallback | None = None,
) -> dict:
    """Entry point — extracts project info, runs clarification check, then full pipeline."""
    _emit(progress_callback, "extract_project_info", "started", None)
    with _log_step("extract_project_info"):
        project_info = _dev_log("extract_project_info", extract_project_info(description), progress_callback)
    _emit(progress_callback, "extract_project_info", "completed", None)

    _emit(progress_callback, "check_requirements", "started", None)
    with _log_step("check_requirements"):
        requirements_check = _dev_log("check_requirements", check_requirements(description), progress_callback)
    _emit(progress_callback, "check_requirements", "completed", None)

    missing_fields = requirements_check.get("missing_fields") or []
    if not missing_fields:
        with _log_step("find_missing_fields"):
            missing_fields = _dev_log("find_missing_fields", find_missing_fields(project_info), progress_callback)

    questions = _dev_log("build_clarification_questions", requirements_check.get("questions") or build_clarification_questions(missing_fields), progress_callback)

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
    """Run the full 11-stage estimation from a resolved project_info dict."""

    # -----------------------------------------------------------------------
    # Stage 1 & 2: Floorplan download + CV
    # -----------------------------------------------------------------------
    floorplan_geometry: dict | None = None
    floorplan_meta: dict = {"available": False}

    if floorplan_image_url:
        _emit(progress_callback, "floorplan_download", "started", {"url": floorplan_image_url})
        try:
            with _log_step("floorplan_download"):
                local_path = _dev_log("download_and_cache", download_and_cache(floorplan_image_url), progress_callback)
            _emit(progress_callback, "floorplan_download", "completed", {"path": local_path})

            _emit(progress_callback, "floorplan_cv", "started", {"path": local_path})
            with _log_step("floorplan_cv"):
                floorplan_geometry = _dev_log("run_floorplan_pipeline", run_floorplan_pipeline(local_path), progress_callback)
            floorplan_meta = {
                "available": True,
                "method": floorplan_geometry.get("method"),
                "total_floor_area_m2": floorplan_geometry.get("total_floor_area_m2"),
                "opening_count": floorplan_geometry.get("opening_count"),
                "room_count": floorplan_geometry.get("room_count"),
            }
            _emit(progress_callback, "floorplan_cv", "completed", floorplan_meta)
        except Exception as exc:
            logger.exception("floorplan_processing_failed url=%s", floorplan_image_url)
            _emit(progress_callback, "floorplan_cv", "failed", {"error": str(exc)})
            floorplan_geometry = None
            floorplan_meta = {"available": False, "error": str(exc)}

    # -----------------------------------------------------------------------
    # Stages 3‑5: BOQ Item Generation (LLM baseline → Item Predictor → LLM gap-fill)
    # -----------------------------------------------------------------------
    _emit(progress_callback, "baseline_boq", "started", None)
    with _log_step("boq_generation"):
        boq_items = _dev_log("build_final_boq_items", build_final_boq_items(project_info, floorplan_geometry), progress_callback)
    _emit(
        progress_callback,
        "baseline_boq",
        "completed",
        {"item_count": len(boq_items)},
    )

    # -----------------------------------------------------------------------
    # Stage 6: RAG — BSR code / unit / rate lookup
    # -----------------------------------------------------------------------
    _emit(progress_callback, "bsr_matching", "started", {"item_count": len(boq_items)})
    with _log_step("bsr_matching", {"item_count": len(boq_items)}):
        boq_items = _dev_log("_match_bsr_items", _match_bsr_items(boq_items), progress_callback)
    _emit(progress_callback, "bsr_matching", "completed", {"item_count": len(boq_items)})

    # -----------------------------------------------------------------------
    # Stage 7: Quantity Take-Off Engine (branching)
    # -----------------------------------------------------------------------
    _emit(progress_callback, "quantity_takeoff", "started", {"item_count": len(boq_items)})
    with _log_step("quantity_takeoff"):
        boq_items = _dev_log("compute_quantities", compute_quantities(boq_items, project_info, floorplan_geometry), progress_callback)
    _emit(progress_callback, "quantity_takeoff", "completed", {"item_count": len(boq_items)})

    # -----------------------------------------------------------------------
    # Stage 8: Validation
    # -----------------------------------------------------------------------
    _emit(progress_callback, "validation", "started", None)
    with _log_step("validation"):
        validation_result = _dev_log("validate_quantities", validate_quantities(boq_items), progress_callback)
    warnings = validation_result.get("warnings") or []
    _emit(progress_callback, "validation", "completed", validation_result)

    # -----------------------------------------------------------------------
    # Stage 9: Cost Calculation
    # -----------------------------------------------------------------------
    _emit(progress_callback, "cost_calculation", "started", None)
    with _log_step("cost_calculation"):
        costs = _dev_log("calculate_costs", calculate_costs(boq_items), progress_callback)
    # Sync cost back onto items list (calculate_costs returns enriched items)
    boq_items = costs.pop("items", boq_items)
    _emit(
        progress_callback,
        "cost_calculation",
        "completed",
        {
            "base_total": costs.get("base_total"),
            "total": costs.get("total"),
        },
    )

    # -----------------------------------------------------------------------
    # Stage 10: Transparency & Confidence Layer
    # -----------------------------------------------------------------------
    _emit(progress_callback, "transparency", "started", None)
    with _log_step("transparency"):
        confidence = _dev_log("score_confidence", score_confidence(project_info, floorplan_geometry, warnings), progress_callback)
        source_summary = _dev_log("_build_source_summary", _build_source_summary(boq_items), progress_callback)
    _emit(progress_callback, "transparency", "completed", {"confidence": confidence, "sources": source_summary})

    # -----------------------------------------------------------------------
    # Stage 11: Reporting
    # -----------------------------------------------------------------------
    _emit(progress_callback, "reporting", "started", None)
    with _log_step("reporting"):
        report_payload = {
            "status": "completed",
            "project_info": project_info,
            "floorplan": floorplan_meta,
            "boq_items": boq_items,
            "costs": costs,
            "validation": validation_result,
            "confidence": confidence,
            "sources": source_summary,
        }
        report = _dev_log("build_report", build_report(report_payload), progress_callback)
    _emit(progress_callback, "reporting", "completed", None)

    return {
        "status": "completed",
        "project_info": project_info,
        "floorplan": floorplan_meta,
        "boq_items": boq_items,
        "costs": costs,
        "validation": validation_result,
        "confidence": confidence,
        "sources": source_summary,
        "report": report,
    }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _emit(
    callback: ProgressCallback | None,
    step: str,
    status: str,
    data: dict | None,
) -> None:
    if callback:
        callback(step, status, data)


@contextmanager
def _log_step(step: str, metadata: dict | None = None) -> Iterator[None]:
    start = time.perf_counter()
    logger.info("step_start step=%s metadata=%s", step, metadata or {})
    try:
        yield
        logger.info("step_ok step=%s", step)
    except Exception:
        logger.exception("step_error step=%s", step)
        raise
    finally:
        ms = (time.perf_counter() - start) * 1000.0
        logger.info("step_end step=%s duration_ms=%.2f", step, ms)


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


def _build_source_summary(items: list[dict]) -> dict:
    """Count how many items' quantities came from each source."""
    summary: dict[str, int] = {}
    for item in items:
        src = item.get("quantity_source") or "unknown"
        summary[src] = summary.get(src, 0) + 1
    return summary

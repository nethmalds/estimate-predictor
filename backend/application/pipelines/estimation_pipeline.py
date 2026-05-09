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

from typing import Callable

from services.clarification_process.service import apply_defaults
from services.item_gen_process.service import build_final_boq_items
from services.floorplan_process.service import run_pipeline as _run_floorplan_facade
from services.floorplan_process.service import merge_floorplan_geometries as _merge_floorplan_geometries
from services.rag_process.service import service as rag_service
from services.quantity_gen_process.service import compute_quantities
from services.pricing_process.service import calculate_costs
from services.reporting_process.service import build_report
from services.reporting_process.service import build_source_summary as _build_source_summary
from services.validation.service import validate_boq_items, score_confidence, validate_quantities


import os

ProgressCallback = Callable[[str, str, dict | None], None]


# ---------------------------------------------------------------------------
# Public entry points
# ---------------------------------------------------------------------------


def run_estimation_pipeline_from_project_info(
    project_info: dict,
    floorplan_urls: list[str] | None = None,
    progress_callback: ProgressCallback | None = None,
) -> dict:
    """Run the full 11-stage estimation from a resolved project_info dict."""

    # Apply Sri Lankan construction defaults for any non-MVED fields not
    # yet set.  Must run before any service that reads parameters.
    project_info = apply_defaults(project_info)

    # -----------------------------------------------------------------------
    # Stage 1 & 2: Floorplan download + CV (one run per uploaded image, merged)
    # -----------------------------------------------------------------------
    floorplan_geometry: dict | None = None
    floorplan_meta: dict = {"available": False}
    floorplan_urls = floorplan_urls or []

    if floorplan_urls:
        _emit(progress_callback, "floorplan_cv", "started", {"url_count": len(floorplan_urls)})
        geometries: list[dict] = []
        for i, url in enumerate(floorplan_urls):
            try:
                geom = _run_floorplan_facade(url)
                geometries.append(geom)
                _emit(progress_callback, "floorplan_cv", "progress",
                      {"url_index": i, "url": url, "area_m2": geom.get("total_floor_area_m2")})
            except Exception as exc:
                _emit(progress_callback, "floorplan_cv", "warning", {"url": url, "error": str(exc)})

        if geometries:
            floorplan_geometry = _merge_floorplan_geometries(geometries)
            floorplan_meta = {
                "available": True,
                "source_count": len(geometries),
                "method": floorplan_geometry.get("method"),
                "total_floor_area_m2": floorplan_geometry.get("total_floor_area_m2"),
                "opening_count": floorplan_geometry.get("opening_count"),
                "room_count": floorplan_geometry.get("room_count"),
                "geometry_confidence": floorplan_geometry.get("geometry_confidence"),
                "scale_source": floorplan_geometry.get("scale_source"),
                "heuristic_flags": floorplan_geometry.get("heuristic_flags"),
            }
            _emit(progress_callback, "floorplan_cv", "completed", floorplan_meta)
        else:
            _emit(progress_callback, "floorplan_cv", "failed", {"error": "All floorplan images failed processing"})
            floorplan_meta = {"available": False, "error": "All images failed"}

    # -----------------------------------------------------------------------
    # Stages 3‑5: BOQ Item Generation (LLM baseline → Item Predictor → LLM gap-fill)
    # -----------------------------------------------------------------------
    _emit(progress_callback, "baseline_boq", "started", None)
    boq_items = build_final_boq_items(project_info, floorplan_geometry, progress_callback=progress_callback)
    _emit(
        progress_callback,
        "baseline_boq",
        "completed",
        {"item_count": len(boq_items)},
    )

    # -----------------------------------------------------------------------
    # Stage 5.5: BOQ Structural Validation (IMP-VAL-01 — moved before RAG)
    # Items lacking description/unit/category are rejected before downstream
    # -----------------------------------------------------------------------
    boq_validation = validate_boq_items(boq_items)

    # -----------------------------------------------------------------------
    # Stage 6: RAG — BSR code / unit / rate lookup
    # -----------------------------------------------------------------------
    _emit(progress_callback, "bsr_matching", "started", {"item_count": len(boq_items)})
    boq_items = rag_service.match_boq_items_batch(boq_items)
    _emit(progress_callback, "bsr_matching", "completed", {"item_count": len(boq_items)})

    # -----------------------------------------------------------------------
    # Stage 7: Quantity Take-Off Engine (branching)
    # -----------------------------------------------------------------------
    _emit(progress_callback, "quantity_takeoff", "started", {"item_count": len(boq_items)})
    boq_items = compute_quantities(boq_items, project_info, floorplan_geometry)
    _emit(progress_callback, "quantity_takeoff", "completed", {"item_count": len(boq_items)})

    # -----------------------------------------------------------------------
    # Stage 8: Validation
    # -----------------------------------------------------------------------
    _emit(progress_callback, "validation", "started", None)
    validation_result = validate_quantities(boq_items)
    warnings = validation_result.get("warnings") or []
    _emit(progress_callback, "validation", "completed", validation_result)

    # -----------------------------------------------------------------------
    # Stage 9: Cost Calculation
    # -----------------------------------------------------------------------
    _emit(progress_callback, "cost_calculation", "started", None)
    costs = calculate_costs(boq_items)
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
    confidence = score_confidence(project_info, floorplan_geometry, warnings, boq_items)
    source_summary = _build_source_summary(boq_items)
    _emit(progress_callback, "transparency", "completed", {"confidence": confidence, "sources": source_summary})

    # -----------------------------------------------------------------------
    # Stage 11: Reporting
    # -----------------------------------------------------------------------
    _emit(progress_callback, "reporting", "started", None)
    report_payload = {
            "project_info": project_info,
            "floorplan": floorplan_meta,
            "boq_items": boq_items,
            "costs": costs,
            "validation": validation_result,
            "confidence": confidence,
            "sources": source_summary,
        }
    report = build_report(report_payload)
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



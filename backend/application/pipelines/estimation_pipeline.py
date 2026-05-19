"""Estimation pipeline — orchestrates the full 11-stage estimation flow.

Stage sequence
--------------
1.  [Optional] Download & cache floorplan image          (floorplan_download)
2.  [Optional] CV pipeline → structured geometry          (floorplan_cv)
2a. [Optional] Floorplan acceptance boundary gate         (floorplan_acceptance)
3.  LLM Initial QS Pass → baseline BOQ (no ML seeds)     (baseline_boq)
4.  Real Item Predictor → additional candidate items      (item_predictor_predictions)
5.  LLM Gap Fill → final BOQ item list                   (gap_fill)
5a. Pre-RAG BOQ structural validation                     (boq_validation)
6.  RAG System → BSR codes / units / rates               (bsr_matching)
7.  Quantity Take-Off Engine (branched)                   (quantity_takeoff)
8.  Validation Layer (ranges + anomalies)                 (validation)
9.  Cost Calculation Engine (qty × rate)                  (cost_calculation)
10. Transparency & Confidence Layer                       (transparency)
11. Reporting Module                                      (reporting)

Floorplan acceptance boundary (Stage 2a)
-----------------------------------------
A merged geometry is accepted only when its ``geometry_confidence`` score is at
or above ``_FLOORPLAN_ACCEPTANCE_THRESHOLD`` (default 0.30).  Below this
threshold the geometry is rejected and downstream stages fall back to the
parametric-only path.  The rejection reason is recorded in ``floorplan_meta``.
"""
from __future__ import annotations

import threading
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
from services.validation.service import validate_boq_items, validate_generated_boq_items, score_confidence, validate_quantities


import os

ProgressCallback = Callable[[str, str, dict | None], None]


class PipelineCancelledError(Exception):
    """Raised when a cooperative cancel signal is detected during pipeline execution."""

# ---------------------------------------------------------------------------
# Floorplan acceptance gate threshold
# ---------------------------------------------------------------------------
# Geometry with confidence below this value is rejected; downstream stages
# fall back to the parametric-only (no-floorplan) path.
_FLOORPLAN_ACCEPTANCE_THRESHOLD: float = float(
    os.environ.get("FLOORPLAN_ACCEPTANCE_THRESHOLD", "0.30")
)


# ---------------------------------------------------------------------------
# Public entry points
# ---------------------------------------------------------------------------


def run_estimation_pipeline_from_project_info(
    project_info: dict,
    floorplan_urls: list[str] | None = None,
    progress_callback: ProgressCallback | None = None,
    cancel_event: threading.Event | None = None,
) -> dict:
    """Run the full 11-stage estimation from a resolved project_info dict."""

    def _check_cancel() -> None:
        """Raise PipelineCancelledError if the cancel signal has been set."""
        if cancel_event is not None and cancel_event.is_set():
            raise PipelineCancelledError("Pipeline cancelled by user request.")

    # Apply Sri Lankan construction defaults for any non-MVED fields not
    # yet set.  Must run before any service that reads parameters.
    project_info = apply_defaults(project_info)

    # -----------------------------------------------------------------------
    # Stage 1 & 2: Floorplan download + CV (one run per uploaded image, merged)
    # -----------------------------------------------------------------------
    floorplan_geometry: dict | None = None
    floorplan_meta: dict = {"available": False}
    floorplan_urls = floorplan_urls or []

    if not floorplan_urls:
        _emit(progress_callback, "floorplan_cv", "skipped", {"reason": "No floorplan images provided"})
        _emit(progress_callback, "floorplan_acceptance", "skipped", {"reason": "No floorplan images provided"})

    if floorplan_urls:
        _emit(progress_callback, "floorplan_cv", "started", {"url_count": len(floorplan_urls)})
        geometries: list[dict] = []
        for i, url in enumerate(floorplan_urls):
            _check_cancel()
            try:
                geom = _run_floorplan_facade(url)
                geometries.append(geom)
                _emit(progress_callback, "floorplan_cv", "progress",
                      {"url_index": i, "url": url, "area_m2": geom.get("total_floor_area_m2")})
            except Exception as exc:
                _emit(progress_callback, "floorplan_cv", "warning", {"url": url, "error": str(exc)})

        if geometries:
            floorplan_geometry = _merge_floorplan_geometries(geometries)
            geo_confidence = float(floorplan_geometry.get("geometry_confidence") or 0.0)

            # ── Stage 2a: Acceptance boundary gate ──────────────────────
            if geo_confidence < _FLOORPLAN_ACCEPTANCE_THRESHOLD:
                rejection_reason = (
                    f"Geometry confidence {geo_confidence:.3f} is below acceptance "
                    f"threshold {_FLOORPLAN_ACCEPTANCE_THRESHOLD:.2f}. "
                    "Falling back to parametric-only path."
                )
                _emit(progress_callback, "floorplan_acceptance", "rejected",
                      {"geometry_confidence": geo_confidence,
                       "threshold": _FLOORPLAN_ACCEPTANCE_THRESHOLD,
                       "reason": rejection_reason})
                # Preserve diagnostic fields before nullifying geometry
                _rejected_scale_source = floorplan_geometry.get("scale_source")
                _rejected_heuristic_flags = floorplan_geometry.get("heuristic_flags")
                floorplan_geometry = None
                floorplan_meta = {
                    "available": False,
                    "accepted": False,
                    "rejection_reason": rejection_reason,
                    "geometry_confidence": geo_confidence,
                    "scale_source": _rejected_scale_source,
                    "heuristic_flags": _rejected_heuristic_flags,
                }
            else:
                floorplan_meta = {
                    "available": True,
                    "accepted": True,
                    "source_count": len(geometries),
                    "method": floorplan_geometry.get("method"),
                    "total_floor_area_m2": floorplan_geometry.get("total_floor_area_m2"),
                    "opening_count": floorplan_geometry.get("opening_count"),
                    "room_count": floorplan_geometry.get("room_count"),
                    "geometry_confidence": geo_confidence,
                    "scale_source": floorplan_geometry.get("scale_source"),
                    "heuristic_flags": floorplan_geometry.get("heuristic_flags"),
                }
                _emit(progress_callback, "floorplan_acceptance", "accepted",
                      {"geometry_confidence": geo_confidence,
                       "threshold": _FLOORPLAN_ACCEPTANCE_THRESHOLD})
                _emit(progress_callback, "floorplan_cv", "completed", floorplan_meta)
        else:
            _emit(progress_callback, "floorplan_cv", "failed", {"error": "All floorplan images failed processing"})
            floorplan_meta = {"available": False, "error": "All images failed"}

    # -----------------------------------------------------------------------
    # Stages 3‑5: BOQ Item Generation (LLM baseline → Item Predictor → LLM gap-fill)
    # -----------------------------------------------------------------------
    _check_cancel()
    _emit(progress_callback, "baseline_boq", "started", None)
    boq_items = build_final_boq_items(project_info, floorplan_geometry, progress_callback=progress_callback)
    _emit(
        progress_callback,
        "baseline_boq",
        "completed",
        {"item_count": len(boq_items)},
    )

    # -----------------------------------------------------------------------
    # Stage 5a: Pre-RAG BOQ Structural Validation
    # Uses the richer validator: checks prelim presence, scope conflicts,
    # source provenance, and structural integrity before BSR retrieval.
    # -----------------------------------------------------------------------
    boq_validation = validate_generated_boq_items(boq_items, project_info)
    boq_validation_warnings: list[str] = (
        (boq_validation.get("errors") or []) +
        (boq_validation.get("warnings") or [])
    )
    _emit(progress_callback, "boq_validation", "completed", {
        "is_valid": boq_validation.get("is_valid"),
        "error_count": len(boq_validation.get("errors") or []),
        "warning_count": len(boq_validation.get("warnings") or []),
    })

    # -----------------------------------------------------------------------
    # Stage 6: RAG — BSR code / unit / rate lookup
    # -----------------------------------------------------------------------
    _check_cancel()
    _emit(progress_callback, "bsr_matching", "started", {"item_count": len(boq_items)})
    boq_items = rag_service.match_boq_items_batch(boq_items)
    _emit(progress_callback, "bsr_matching", "completed", {"item_count": len(boq_items)})

    # -----------------------------------------------------------------------
    # Stage 6a: Post-RAG BSR Retrieval Validation
    # Items with no BSR match are dropped here — they carry no rate or unit
    # so they cannot contribute to cost and would only introduce noise in
    # quantity take-off.  Soft-match items with zero rate are flagged for
    # review but retained.  Items with a matched BSR code but no unit are
    # also flagged.
    # -----------------------------------------------------------------------
    post_rag_warnings: list[str] = []
    matched_items: list[dict] = []
    for _item in boq_items:
        _mt = _item.get("match_type", "no_match")
        _rate = float(_item.get("rate") or 0.0)
        _desc = (_item.get("description") or "")[:60]
        if _mt == "no_match":
            post_rag_warnings.append(
                f"'{_desc}': no BSR match found — item dropped before quantity take-off."
            )
            continue  # drop — not added to matched_items
        if _mt == "soft_match" and _rate <= 0.0:
            post_rag_warnings.append(
                f"'{_desc}': soft BSR match has zero rate — marked for review."
            )
            _item["needs_rate_review"] = True
        # Validate unit propagation: BSR unit must be set for non-contractual items
        if _mt not in ("contractual",) and not (_item.get("unit") or "").strip():
            post_rag_warnings.append(
                f"'{_desc}': BSR match returned no unit — quantity calculation may be unreliable."
            )
        matched_items.append(_item)

    dropped_count = len(boq_items) - len(matched_items)
    boq_items = matched_items

    _emit(progress_callback, "bsr_validation", "completed", {
        "warning_count": len(post_rag_warnings),
        "warnings": post_rag_warnings[:5],   # surface first 5 to SSE
        "dropped_count": dropped_count,
        "retained_count": len(boq_items),
    })

    # -----------------------------------------------------------------------
    # Stage 7: Quantity Take-Off Engine (branching)
    # -----------------------------------------------------------------------
    _check_cancel()
    _emit(progress_callback, "quantity_takeoff", "started", {"item_count": len(boq_items)})
    boq_items = compute_quantities(boq_items, project_info, floorplan_geometry)
    _emit(progress_callback, "quantity_takeoff", "completed", {"item_count": len(boq_items)})

    # -----------------------------------------------------------------------
    # Stage 8: Validation
    # -----------------------------------------------------------------------
    _check_cancel()
    _emit(progress_callback, "validation", "started", None)
    validation_result = validate_quantities(boq_items)
    _emit(progress_callback, "validation", "completed", validation_result)

    # -----------------------------------------------------------------------
    # Stage 9: Cost Calculation
    # -----------------------------------------------------------------------
    _check_cancel()
    _emit(progress_callback, "cost_calculation", "started", None)
    costs = calculate_costs(boq_items)
    # Sync cost back onto items list (calculate_costs returns enriched items)
    boq_items = costs.pop("items", boq_items)
    cost_consistency_warnings: list[str] = costs.pop("consistency_warnings", [])
    _emit(
        progress_callback,
        "cost_calculation",
        "completed",
        {
            "base_total": costs.get("base_total"),
            "external_works_total": costs.get("external_works_total"),
            "total": costs.get("total"),
        },
    )

    # Assemble unified warnings from all stages — done here so cost warnings are included
    warnings: list[str] = (
        list(boq_validation_warnings)
        + list(post_rag_warnings)
        + (validation_result.get("warnings") or [])
        + list(cost_consistency_warnings)
    )
    validation_result["warnings"] = warnings

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



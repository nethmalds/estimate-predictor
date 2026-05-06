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

from services.clarification_process.clarification_agent import apply_defaults
from services.item_gen_process.service import build_final_boq_items
from services.floorplan_process.service import run_pipeline as _run_floorplan_facade
from services.rag_process.service import service as rag_service
from services.quantity_gen_process.service import compute_quantities
from services.pricing_process.cost_calculator import calculate_costs
from services.reporting_process.report_builder import build_report
from services.validation.boq_validator import validate_boq_items
from services.validation.confidence_scoring import score_confidence
from services.validation.quantity_validator import validate_quantities
from core.logging.logger import ensure_logging, get_logger, log_payload

logger = get_logger(__name__)

import os
from typing import Any

ProgressCallback = Callable[[str, str, dict | None], None]


def _dev_log(step_name: str, output: Any, cb: ProgressCallback | None = None) -> Any:
    """Log payload to payloads.log AND push a dev_log event to the pipeline trace."""
    log_payload(step_name, output)
    if cb:
        # status="dev_log" signals the progress callback to write to trace_queue
        # without sending it over the main SSE stream to the user.
        cb(step_name, "dev_log", output if isinstance(output, dict) else {"data": str(output)[:500]})
    return output


# ---------------------------------------------------------------------------
# Public entry points
# ---------------------------------------------------------------------------


def run_estimation_pipeline_from_project_info(
    project_info: dict,
    floorplan_urls: list[str] | None = None,
    progress_callback: ProgressCallback | None = None,
) -> dict:
    """Run the full 11-stage estimation from a resolved project_info dict."""
    ensure_logging()

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
                with _log_step(f"floorplan_cv_{i}"):
                    geom = _dev_log(
                        f"run_floorplan_pipeline_{i}",
                        _run_floorplan_facade(url),
                        progress_callback,
                    )
                geometries.append(geom)
                _emit(progress_callback, "floorplan_cv", "progress",
                      {"url_index": i, "url": url, "area_m2": geom.get("total_floor_area_m2")})
            except Exception as exc:
                logger.exception("floorplan_cv_failed url=%s", url)
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
    with _log_step("boq_generation"):
        boq_items = _dev_log("build_final_boq_items", build_final_boq_items(project_info, floorplan_geometry, progress_callback=progress_callback), progress_callback)
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
        boq_items = _dev_log("_match_bsr_items", _match_bsr_items(boq_items, progress_callback), progress_callback)
    _emit(progress_callback, "bsr_matching", "completed", {"item_count": len(boq_items)})

    # -----------------------------------------------------------------------
    # Stage 7: Quantity Take-Off Engine (branching)
    # -----------------------------------------------------------------------
    _emit(progress_callback, "quantity_takeoff", "started", {"item_count": len(boq_items)})
    with _log_step("quantity_takeoff"):
        boq_items = _dev_log("compute_quantities", compute_quantities(boq_items, project_info, floorplan_geometry), progress_callback)
    _emit(progress_callback, "quantity_takeoff", "completed", {"item_count": len(boq_items)})

    # -----------------------------------------------------------------------
    # Stage 7.5: BOQ Structural Validation (Q2 fix)
    # -----------------------------------------------------------------------
    with _log_step("boq_validation"):
        boq_validation = validate_boq_items(boq_items)
        _dev_log("boq_validation", boq_validation, progress_callback)
        if not boq_validation["is_valid"]:
            logger.warning(
                "boq_validation_errors errors=%s",
                boq_validation["errors"],
            )

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
        confidence = _dev_log(
            "score_confidence",
            score_confidence(project_info, floorplan_geometry, warnings, boq_items),
            progress_callback,
        )
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


# Keywords that identify contractual/financial items that have no BSR rate.
_CONTRACTUAL_KEYWORDS = {
    "performance security",
    "advance payment security",
    "advance payment bond",
    "advance bond",
    "lump sum",
}


def _is_contractual_item(item: dict) -> bool:
    """Return True for financial/contractual items that cannot be BSR-matched."""
    desc = (item.get("description") or "").lower()
    cat = (item.get("category") or "").lower()
    if cat == "preliminary_and_general":
        return True
    return any(kw in desc for kw in _CONTRACTUAL_KEYWORDS)


def _match_bsr_items(items: list[dict], progress_callback: ProgressCallback | None = None) -> list[dict]:
    matched: list[dict] = []
    unmatched_items: list[dict] = []
    soft_matched_items: list[dict] = []

    for item in items:
        description = item.get("description") or ""

        # --- Fix 4: bypass RAG for contractual / preliminary items ---
        if _is_contractual_item(item):
            merged = dict(item)
            merged.update(
                {
                    "bsr_item_no": "CONTRACTUAL",
                    "bsr_description": None,
                    "unit": "item",
                    "rate": 0.0,
                    "match_confidence": 0.0,
                    "match_type": "contractual",
                    "needs_rate_review": True,
                }
            )
            matched.append(merged)
            unmatched_items.append(merged)   # still reported for user awareness
            continue

        bsr_match = rag_service.match_boq_item(description)
        merged = dict(item)
        merged.update(
            {
                "bsr_item_no": bsr_match.get("item_no"),
                "bsr_description": bsr_match.get("description"),
                "unit": bsr_match.get("unit"),
                "rate": bsr_match.get("rate") or 0.0,
                "match_confidence": bsr_match.get("confidence"),
                "match_type": bsr_match.get("match_type", "no_match"),
                "needs_rate_review": bsr_match.get("needs_rate_review", False),
            }
        )
        matched.append(merged)

        item_no = bsr_match.get("item_no")
        match_type = bsr_match.get("match_type", "no_match")

        if item_no == "NO_MATCH":
            unmatched_items.append(merged)
        elif match_type == "soft_match":
            soft_matched_items.append(merged)

    # --- Report unmatched items ---
    if unmatched_items:
        logger.warning("========== [UNMATCHED BSR ITEMS] ==========")
        logger.warning("Total unmatched items: %d", len(unmatched_items))
        for i, item in enumerate(unmatched_items, 1):
            logger.warning("%d. [%s] %s", i, item.get("category"), item.get("description"))
        logger.warning("===========================================")
        logger.warning("bsr_matching_unmatched_count count=%d", len(unmatched_items))

        log_payload(
            "bsr_matching_unmatched",
            {
                "unmatched_count": len(unmatched_items),
                "unmatched_items": [
                    {
                        "category": item.get("category"),
                        "description": item.get("description"),
                        "match_type": item.get("match_type"),
                    }
                    for item in unmatched_items
                ],
            },
        )

    # --- Report soft-matched items (borderline — user should review rates) ---
    if soft_matched_items:
        logger.warning("========== [SOFT-MATCHED BSR ITEMS] ==========")
        logger.warning("Total soft-matched items: %d", len(soft_matched_items))
        for i, item in enumerate(soft_matched_items, 1):
            logger.warning(
                "%d. [%s] %s  →  BSR:%s (conf=%.3f)",
                i,
                item.get("category"),
                item.get("description"),
                item.get("bsr_item_no"),
                item.get("match_confidence") or 0.0,
            )
        logger.warning("===============================================")

        log_payload(
            "bsr_matching_soft",
            {
                "soft_match_count": len(soft_matched_items),
                "soft_match_items": [
                    {
                        "category": item.get("category"),
                        "description": item.get("description"),
                        "bsr_item_no": item.get("bsr_item_no"),
                        "confidence": item.get("match_confidence"),
                    }
                    for item in soft_matched_items
                ],
            },
        )

    return matched


def _build_source_summary(items: list[dict]) -> dict:
    """Count items by source type for transparency reporting (Phase 13).

    Categorises each item into one of these buckets:
    - geometry_only       : single geometry/rule candidate, no ML fusion
    - parametric_only     : single parametric candidate, no ML fusion
    - ml_only             : single ML candidate (item-level)
    - fused               : 2+ candidates were weighted-fused
    - globally_allocated  : quantity derived from category-level ML global model
    - low_confidence      : quantity_confidence < 0.50
    - discretely_rounded  : discrete unit item (whole-number check applied)
    - unknown             : no other category matched
    """
    _DISCRETE_UNITS = frozenset({"nr", "nr.", "no", "no.", "item", "pair", "set", "each", "lot"})

    summary: dict[str, int] = {
        "geometry_only": 0,
        "parametric_only": 0,
        "ml_only": 0,
        "fused": 0,
        "globally_allocated": 0,
        "low_confidence": 0,
        "discretely_rounded": 0,
        "unknown": 0,
    }

    for item in items:
        candidates = item.get("quantity_candidates") or []
        recon = item.get("reconciliation_summary") or {}
        review_flags = recon.get("review_flags") or []
        candidate_count = recon.get("candidate_count") or len(candidates)
        source = item.get("quantity_source") or "unknown"
        unit = str(item.get("unit") or item.get("preferred_unit") or "").lower().strip()
        conf = float(item.get("quantity_confidence") or item.get("quantity_confidence_score") or 0.0)

        # Discrete rounding bucket (additive — item may also be in another bucket)
        if unit in _DISCRETE_UNITS:
            summary["discretely_rounded"] += 1

        # Low confidence (additive)
        if conf < 0.50:
            summary["low_confidence"] += 1

        # Global allocation check
        if "global_allocation_only" in review_flags or "global_allocation_used" in review_flags:
            summary["globally_allocated"] += 1
            continue

        # Fused: multiple candidates
        if candidate_count >= 2:
            summary["fused"] += 1
            continue

        # Single-candidate buckets
        cand_types = [c.get("candidate_type", "") for c in candidates] if candidates else [source]
        if any(t in ("geometry", "rule_based") for t in cand_types):
            summary["geometry_only"] += 1
        elif any(t == "parametric" for t in cand_types):
            summary["parametric_only"] += 1
        elif any(t in ("ml_item_level", "quantity_predictor") for t in cand_types):
            summary["ml_only"] += 1
        else:
            summary["unknown"] += 1

    return summary


# ---------------------------------------------------------------------------
# Multi-image geometry merge
# ---------------------------------------------------------------------------

_SCALE_PRIORITY = ["ocr_confirmed", "ocr_dimensions", "detector", "heuristic"]


def _merge_floorplan_geometries(geometries: list[dict]) -> dict:
    """Merge geometry dicts from multiple floorplan images into one aggregate.

    Strategy
    --------
    - Numeric totals (area, perimeter, walls, openings, rooms): **sum**.
    - Geometry confidence: **weighted average** by individual confidence scores.
    - Scale source: pick the **most reliable** value per ``_SCALE_PRIORITY``.
    - Heuristic flags: **OR** — flag is True if any image raised it.
    - Rooms list: concatenated.
    - Method: set to ``"multi_image_merged"``.
    """
    if not geometries:
        return {}
    if len(geometries) == 1:
        return geometries[0]

    total_area = sum(g.get("total_floor_area_m2", 0.0) for g in geometries)
    total_perimeter = sum(g.get("perimeter_m", 0.0) for g in geometries)
    total_walls = sum(g.get("wall_length_m", 0.0) for g in geometries)
    total_openings = sum(g.get("opening_count", 0) for g in geometries)
    total_rooms = sum(g.get("room_count", 0) for g in geometries)
    all_rooms = [r for g in geometries for r in (g.get("rooms") or [])]

    confs = [float(g.get("geometry_confidence", 0.0)) for g in geometries]
    avg_conf = sum(confs) / len(confs)

    best_scale = min(
        (g.get("scale_source", "heuristic") for g in geometries),
        key=lambda s: _SCALE_PRIORITY.index(s) if s in _SCALE_PRIORITY else 99,
    )

    _FLAG_KEYS = (
        "derived_from_area_only",
        "assumed_floor_height",
        "inferred_internal_walls",
        "missing_scale_confirmation",
    )
    merged_flags: dict[str, bool] = {
        key: any(g.get("heuristic_flags", {}).get(key, False) for g in geometries)
        for key in _FLAG_KEYS
    }

    return {
        "total_floor_area_m2": round(total_area, 2),
        "perimeter_m": round(total_perimeter, 2),
        "wall_length_m": round(total_walls, 2),
        "opening_count": total_openings,
        "room_count": total_rooms,
        "rooms": all_rooms,
        "geometry_confidence": round(avg_conf, 4),
        "scale_source": best_scale,
        "heuristic_flags": merged_flags,
        "method": "multi_image_merged",
        "source_count": len(geometries),
        "inferred_area_flag": any(g.get("inferred_area_flag", False) for g in geometries),
    }

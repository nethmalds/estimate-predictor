"""Floorplan processing orchestrator.

Owns the end-to-end floorplan CV flow.  All floorplan business logic lives
here; ``service.py`` is the communication facade that delegates inward.

Geometry dict shape returned
-----------------------------
{
    "total_floor_area_m2": float,
    "perimeter_m":         float,
    "wall_length_m":       float,
    "opening_count":       int,
    "room_count":          int,
    "rooms":               list[{"label": str, "area_m2": float}],
    "dimensions_raw":      list[str],
    "method":              str,  # "ocr_dimensions" | "ocr_text_only" | "placeholder"

    # Geometry confidence breakdown
    "geometry_confidence":    float,   # 0–1 aggregate score (c_g)
    "scale_source":           str,     # how scale was established
    "dimensions_confidence":  float,   # 0–1 OCR dimension quality signal
    "openings_confidence":    float,   # 0–1 YOLO opening detection quality
    "coverage_confidence":    float,   # 0–1 room-area coverage proxy

    # Heuristic flags
    "heuristic_flags": {
        "derived_from_area_only":      bool,
        "assumed_floor_height":        bool,
        "inferred_internal_walls":     bool,
        "missing_scale_confirmation":  bool,
    },
    "inferred_area_flag": bool,

    # Legacy / internal
    "_yolo_avg_conf": float,
    "_preprocess":    dict,
    "_ocr":           dict,
}
"""
from __future__ import annotations

import math
import re

from services.floorplan_process.confidence_scorer import compute_geometry_confidence
from services.floorplan_process.geometry_extraction.geometry_extractor import (
    detect_openings,
    extract_room_boundaries,
    get_detection_confidence,
    preprocess_image,
)
from services.floorplan_process.geometry_extraction.ocr import (
    extract_floorplan_text_and_dimensions,
)
from services.floorplan_process.image_cache import download_and_cache
from core.logging.logger import get_logger

logger = get_logger(__name__)

# Assumed floor-to-ceiling height for wall-length estimates (metres)
_DEFAULT_FLOOR_HEIGHT_M = 3.0


def _rasterize_pdf(pdf_path: str) -> str:
    """Rasterize the first page of a PDF to a PNG file beside the original.

    Returns the path to the rasterized PNG.  Requires PyMuPDF (``fitz``).
    """
    try:
        import fitz  # PyMuPDF
    except ImportError as exc:
        raise ImportError(
            "PyMuPDF is required for PDF rasterization. "
            "Install with: pip install PyMuPDF"
        ) from exc

    png_path = pdf_path.rsplit(".", 1)[0] + "_p1.png"
    doc = fitz.open(pdf_path)
    try:
        page = doc[0]
        mat = fitz.Matrix(2.0, 2.0)  # 2× scale → ~144 dpi for crisp OCR
        pix = page.get_pixmap(matrix=mat)
        pix.save(png_path)
    finally:
        doc.close()
    logger.info("floorplan_orchestrator pdf_rasterized pdf=%s png=%s", pdf_path, png_path)
    return png_path


def run_floorplan_pipeline(image_path: str) -> dict:
    """Run the full CV pipeline on *image_path* (local path or remote URL).

    If *image_path* is an http(s) URL it is downloaded and cached locally
    using ``image_cache.download_and_cache`` before processing.
    PDF files are rasterized to PNG before OCR/YOLO so the full geometry
    pipeline can operate on a standard raster image.

    Returns
    -------
    dict
        Enriched geometry dict including confidence breakdown and
        heuristic flags.
    """
    # ── Resolve remote URL to local path ────────────────────────────────────
    if image_path.startswith(("http://", "https://")):
        logger.info("floorplan_orchestrator resolving remote url=%s", image_path)
        image_path = download_and_cache(image_path)

    # ── Rasterize PDF to PNG before OCR/YOLO ────────────────────────────────
    if image_path.lower().endswith(".pdf"):
        logger.info("floorplan_orchestrator rasterizing pdf path=%s", image_path)
        image_path = _rasterize_pdf(image_path)

    logger.info("floorplan_orchestrator start image_path=%s", image_path)

    # ── Raw extraction adapters ──────────────────────────────────────────────
    preprocess = preprocess_image(image_path)
    ocr_result = extract_floorplan_text_and_dimensions(image_path)

    openings_raw   = detect_openings(image_path)
    rooms_raw      = extract_room_boundaries(image_path)
    yolo_avg_conf  = get_detection_confidence(image_path)   # LRU-cached — no extra cost

    # ── Dimension / OCR signals ─────────────────────────────────────────────
    dimensions_raw: list[str] = ocr_result.get("dimensions") or []
    dimensions_confidence = 1.0 if dimensions_raw else 0.0

    # ── Rooms & area ────────────────────────────────────────────────────────
    room_list: list[dict] = rooms_raw.get("rooms") or []
    room_structs = [_normalise_room(r) for r in room_list]

    total_floor_area_m2 = sum(r["area_m2"] for r in room_structs)

    # Track how the area was established for scale_source + heuristic flags
    inferred_area_flag  = False
    scale_source        = "detector"

    if total_floor_area_m2 > 0 and dimensions_raw:
        scale_source = "ocr_confirmed"
    elif total_floor_area_m2 == 0.0 and dimensions_raw:
        total_floor_area_m2 = _infer_area_from_dimensions(dimensions_raw)
        if total_floor_area_m2 > 0:
            scale_source = "ocr_dimensions"

    if total_floor_area_m2 == 0.0:
        inferred_area_flag = True
        scale_source       = "heuristic"

    method = "ocr_dimensions" if dimensions_raw else "ocr_text_only"

    # ── Perimeter & wall lengths ─────────────────────────────────────────────
    # Approximation: assume roughly square footprint → perimeter ≈ 4√A
    perimeter_m = 4.0 * math.sqrt(total_floor_area_m2) if total_floor_area_m2 > 0 else 0.0

    # Internal walls: sum of room diagonals when rooms are available, else 60 % of perimeter
    internal_wall_estimate = sum(
        math.sqrt(r["area_m2"]) * 2 for r in room_structs if r["area_m2"] > 0
    )
    inferred_internal_walls = False
    if internal_wall_estimate == 0.0 and total_floor_area_m2 > 0:
        internal_wall_estimate  = perimeter_m * 0.6
        inferred_internal_walls = True

    wall_length_m = perimeter_m + internal_wall_estimate

    # ── Heuristic flags ──────────────────────────────────────────────────────
    derived_from_area_only = len(room_structs) == 0 and total_floor_area_m2 > 0
    heuristic_flags: dict[str, bool] = {
        "derived_from_area_only":     derived_from_area_only,
        "assumed_floor_height":       True,   # always assumed at current stage
        "inferred_internal_walls":    inferred_internal_walls,
        "missing_scale_confirmation": scale_source in ("heuristic", "area_inferred"),
    }

    # ── Openings ─────────────────────────────────────────────────────────────
    doors:        int = openings_raw.get("doors") or 0
    windows:      int = openings_raw.get("windows") or 0
    opening_count: int = doors + windows

    # ── Confidence components ─────────────────────────────────────────────────
    openings_confidence  = float(yolo_avg_conf or 0.0)
    coverage_confidence  = min(len(room_structs) / 5.0, 1.0)
    geometry_confidence  = compute_geometry_confidence(
        ocr_confidence      = dimensions_confidence,
        detector_confidence = float(yolo_avg_conf or 0.0),
        scale_source        = scale_source,
        coverage_confidence = coverage_confidence,
        heuristic_flags     = heuristic_flags,
    )

    # ── Assemble geometry dict ────────────────────────────────────────────────
    geometry = {
        "total_floor_area_m2": round(total_floor_area_m2, 2),
        "perimeter_m":         round(perimeter_m, 2),
        "wall_length_m":       round(wall_length_m, 2),
        "opening_count":       opening_count,
        "room_count":          len(room_structs),
        "rooms":               room_structs,
        "dimensions_raw":      dimensions_raw,
        "method":              method,
        # Geometry confidence breakdown
        "geometry_confidence":   geometry_confidence,
        "scale_source":          scale_source,
        "dimensions_confidence": round(dimensions_confidence, 4),
        "openings_confidence":   round(openings_confidence, 4),
        "coverage_confidence":   round(coverage_confidence, 4),
        # Heuristic flags
        "heuristic_flags":    heuristic_flags,
        "inferred_area_flag": inferred_area_flag,
        # Legacy / internal compatibility
        "_yolo_avg_conf": yolo_avg_conf,
        "_preprocess":    preprocess,
        "_ocr":           ocr_result,
    }

    logger.info(
        "floorplan_orchestrator done method=%s area_m2=%.1f openings=%d "
        "rooms=%d geo_conf=%.4f scale_source=%s",
        method, total_floor_area_m2, opening_count,
        len(room_structs), geometry_confidence, scale_source,
    )
    return geometry


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _normalise_room(raw: dict) -> dict:
    """Ensure a room entry has at least a label and area_m2 field."""
    area = raw.get("area_m2") or raw.get("area") or 0.0
    try:
        area = float(area)
    except (TypeError, ValueError):
        area = 0.0
    return {
        "label":   str(raw.get("label") or raw.get("name") or "room"),
        "area_m2": round(area, 2),
    }


def _infer_area_from_dimensions(dimensions: list[str]) -> float:
    """Best-effort: multiply the two largest metric values found in OCR text.

    Handles simple cases like '10m x 8m' floor labels.
    Returns 0.0 when fewer than two usable values are found.
    """
    values_m: list[float] = []
    for token in dimensions:
        m = re.search(r"([\d.]+)\s*m\b", token, re.IGNORECASE)
        if m:
            try:
                values_m.append(float(m.group(1)))
            except ValueError:
                pass
    values_m.sort(reverse=True)
    if len(values_m) >= 2:
        return values_m[0] * values_m[1]
    return 0.0

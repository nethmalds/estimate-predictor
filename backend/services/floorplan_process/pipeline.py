"""Floorplan CV pipeline — processes a local image file and returns a
standardised geometry dict that the Quantity Take-Off Engine can consume.

The geometry dict shape (all values are floats / ints):
    {
        "total_floor_area_m2": float,
        "perimeter_m": float,
        "wall_length_m": float,
        "opening_count": int,
        "room_count": int,
        "rooms": [{"label": str, "area_m2": float}],
        "dimensions_raw": list[str],
        "method": str,  # "ocr_dimensions" | "ocr_text_only" | "placeholder"
    }
"""
from __future__ import annotations

import math

from services.floorplan_process.geometry_extraction.geometry_extractor import (
    detect_openings,
    extract_room_boundaries,
    preprocess_image,
)
from services.floorplan_process.image_cache import download_and_cache
from services.floorplan_process.service import service
from core.logging.logger import get_logger

logger = get_logger(__name__)

# Assumed floor-to-ceiling height used for wall-length estimates (metres)
_DEFAULT_FLOOR_HEIGHT_M = 3.0


def run_floorplan_pipeline(image_path: str) -> dict:
    """Run the full CV pipeline on *image_path* (local path or remote URL).

    If *image_path* is an http(s) URL it is downloaded and cached locally
    using ``image_cache.download_and_cache`` before processing.
    """
    # ── Resolve remote URL to local path ────────────────────────────────────
    if image_path.startswith(("http://", "https://")):
        logger.info("floorplan_pipeline resolving remote url=%s", image_path)
        image_path = download_and_cache(image_path)

    logger.info("floorplan_pipeline start image_path=%s", image_path)

    preprocess = preprocess_image(image_path)
    ocr_result = service.extract_dimensions(image_path)
    openings_raw = detect_openings(image_path)
    rooms_raw = extract_room_boundaries(image_path)

    dimensions_raw: list[str] = ocr_result.get("dimensions") or []
    method = "ocr_dimensions" if dimensions_raw else "ocr_text_only"

    # --- Rooms ----------------------------------------------------------
    room_list: list[dict] = rooms_raw.get("rooms") or []
    room_structs = [_normalise_room(r) for r in room_list]

    # --- Areas ----------------------------------------------------------
    total_floor_area_m2 = sum(r["area_m2"] for r in room_structs)

    # If CV returned no room areas, try to infer from parsed OCR dimensions
    if total_floor_area_m2 == 0.0:
        total_floor_area_m2 = _infer_area_from_dimensions(dimensions_raw)
        if total_floor_area_m2 > 0:
            method = "ocr_dimensions"

    # --- Perimeter & wall lengths ---------------------------------------
    # Approximation: assume roughly square footprint → perimeter ≈ 4√A
    perimeter_m = 4.0 * math.sqrt(total_floor_area_m2) if total_floor_area_m2 > 0 else 0.0

    # Total wall length = perimeter + internal walls (estimated as √A per room)
    internal_wall_estimate = sum(
        math.sqrt(r["area_m2"]) * 2 for r in room_structs if r["area_m2"] > 0
    )
    if internal_wall_estimate == 0.0 and total_floor_area_m2 > 0:
        # Rough heuristic: internal walls ≈ 60 % of perimeter
        internal_wall_estimate = perimeter_m * 0.6

    wall_length_m = perimeter_m + internal_wall_estimate

    # --- Openings -------------------------------------------------------
    doors: int = openings_raw.get("doors") or 0
    windows: int = openings_raw.get("windows") or 0
    opening_count: int = doors + windows

    geometry = {
        "total_floor_area_m2": round(total_floor_area_m2, 2),
        "perimeter_m": round(perimeter_m, 2),
        "wall_length_m": round(wall_length_m, 2),
        "opening_count": opening_count,
        "room_count": len(room_structs),
        "rooms": room_structs,
        "dimensions_raw": dimensions_raw,
        "method": method,
        # carry through raw sub-results for diagnostics
        "_preprocess": preprocess,
        "_ocr": ocr_result,
    }

    logger.info(
        "floorplan_pipeline done method=%s area_m2=%.1f openings=%d rooms=%d",
        method,
        total_floor_area_m2,
        opening_count,
        len(room_structs),
    )
    return geometry


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _normalise_room(raw: dict) -> dict:
    """Ensure a room entry has at least a label and area_m2 field."""
    area = raw.get("area_m2") or raw.get("area") or 0.0
    try:
        area = float(area)
    except (TypeError, ValueError):
        area = 0.0
    return {
        "label": str(raw.get("label") or raw.get("name") or "room"),
        "area_m2": round(area, 2),
    }


def _infer_area_from_dimensions(dimensions: list[str]) -> float:
    """Best-effort: multiply the two largest metric values found in OCR text.

    This handles simple cases like '10m x 8m' floor labels.
    Returns 0.0 if fewer than two usable values are found.
    """
    import re
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


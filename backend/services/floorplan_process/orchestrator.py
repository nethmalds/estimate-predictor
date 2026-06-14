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

import logging
import math
import re
import warnings

_log = logging.getLogger(__name__)

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


# Assumed floor-to-ceiling height for wall-length estimates (metres)
_DEFAULT_FLOOR_HEIGHT_M = 3.0


def _placeholder_geometry(skip_reason: str) -> dict:
    """Return a fully-valid zero-valued geometry dict for when the image cannot be loaded."""
    heuristic_flags = {
        "derived_from_area_only": False,
        "assumed_floor_height": True,
        "inferred_internal_walls": False,
        "missing_scale_confirmation": True,
    }
    return {
        "total_floor_area_m2": 0.0,
        "perimeter_m": 0.0,
        "wall_length_m": 0.0,
        "opening_count": 0,
        "room_count": 0,
        "rooms": [],
        "dimensions_raw": [],
        "method": "placeholder",
        "geometry_confidence": 0.0,
        "scale_source": "heuristic",
        "dimensions_confidence": 0.0,
        "openings_confidence": 0.0,
        "coverage_confidence": 0.0,
        "heuristic_flags": heuristic_flags,
        "inferred_area_flag": True,
        "_yolo_avg_conf": 0.0,
        "_preprocess": {},
        "_ocr": {},
        "_ocr_succeeded": False,
        "_yolo_succeeded": False,
        "_skip_reason": skip_reason,
    }


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
        try:
            image_path = download_and_cache(image_path)
        except Exception as exc:
            warnings.warn(
                f"[orchestrator] Failed to download {image_path!r}: {exc}. "
                "Returning placeholder geometry.",
                stacklevel=2,
            )
            return _placeholder_geometry(f"download_failed: {exc}")

    # ── Rasterize PDF to PNG before OCR/YOLO ────────────────────────────────
    if image_path.lower().endswith(".pdf"):
        try:
            image_path = _rasterize_pdf(image_path)
        except Exception as exc:
            warnings.warn(
                f"[orchestrator] Failed to rasterize PDF {image_path!r}: {exc}. "
                "Returning placeholder geometry.",
                stacklevel=2,
            )
            return _placeholder_geometry(f"pdf_rasterize_failed: {exc}")

    # ── Raw extraction adapters ──────────────────────────────────────────────
    try:
        preprocess = preprocess_image(image_path)
    except Exception as exc:
        warnings.warn(
            f"[orchestrator] preprocess_image failed for {image_path!r}: {exc}. "
            "Continuing with empty preprocess.",
            stacklevel=2,
        )
        preprocess = {
            "image_path":     image_path,
            "processed_path": image_path,
            "size_bytes":     0,
            "format":         "unknown",
            "method":         "failed",
        }

    processed_path = preprocess.get("processed_path") or image_path

    # OCR step — degrade gracefully if Tesseract unavailable
    _ocr_succeeded = False
    try:
        ocr_result = extract_floorplan_text_and_dimensions(
            processed_path, original_path=image_path
        )
        _ocr_succeeded = True
    except Exception as exc:
        warnings.warn(
            f"[orchestrator] OCR failed for {image_path!r}: {exc}. "
            "Continuing with empty dimensions.",
            stacklevel=2,
        )
        ocr_result = {
            "image_path": image_path, "text": "", "dimensions": [],
            "dimension_count": 0, "ocr_skipped": True, "ocr_skip_reason": str(exc),
        }

    # YOLO step — degrade gracefully if model unavailable or inference fails
    _yolo_succeeded = False
    try:
        openings_raw  = detect_openings(processed_path)
        rooms_raw     = extract_room_boundaries(processed_path)
        yolo_avg_conf = get_detection_confidence(processed_path)   # LRU-cached — no extra cost
        _yolo_succeeded = True
    except Exception as exc:
        warnings.warn(
            f"[orchestrator] YOLO failed for {image_path!r}: {exc}. "
            "Continuing with empty detections.",
            stacklevel=2,
        )
        openings_raw  = {"doors": 0, "windows": 0, "method": "yolo_failed"}
        rooms_raw     = {"rooms": [], "method": "yolo_failed"}
        yolo_avg_conf = 0.0

    # ── Dimension / OCR signals ─────────────────────────────────────────────
    dimensions_raw: list[str] = ocr_result.get("dimensions") or []
    dimensions_confidence = 1.0 if dimensions_raw else 0.0
    ocr_labels: list[dict] = ocr_result.get("ocr_labels") or []

    # ── Rooms & area ────────────────────────────────────────────────────────
    room_list: list[dict] = rooms_raw.get("rooms") or []
    img_w = int(rooms_raw.get("img_w") or 0)
    img_h = int(rooms_raw.get("img_h") or 0)

    # Map vision-API room labels onto YOLO zones by centroid proximity.
    if ocr_labels and room_list and img_w > 0 and img_h > 0:
        room_list = _match_zones_to_labels(room_list, ocr_labels, img_w, img_h)

    room_structs = [_normalise_room(r) for r in room_list]

    yolo_area_m2 = sum(r["area_m2"] for r in room_structs)

    # Prefer OCR-derived area when room dimension labels are available: summing
    # all W×H pairs is more accurate than YOLO's pixel→m² heuristic.
    ocr_area_m2 = 0.0
    if dimensions_raw:
        ocr_area_m2 = _sum_room_areas_from_dimensions(dimensions_raw)
        if ocr_area_m2 == 0.0:
            ocr_area_m2 = _infer_area_from_dimensions(dimensions_raw)

    # Track how the area was established for scale_source + heuristic flags
    inferred_area_flag  = False
    scale_source        = "detector"

    if ocr_area_m2 > 0 and yolo_area_m2 > 0:
        total_floor_area_m2 = ocr_area_m2
        scale_source = "ocr_confirmed"
    elif ocr_area_m2 > 0:
        total_floor_area_m2 = ocr_area_m2
        scale_source = "ocr_dimensions"
    elif yolo_area_m2 > 0:
        total_floor_area_m2 = yolo_area_m2
        scale_source = "detector"
    else:
        total_floor_area_m2 = 0.0

    if total_floor_area_m2 == 0.0:
        inferred_area_flag = True
        scale_source       = "heuristic"

    method = "ocr_dimensions" if dimensions_raw else "ocr_text_only"

    # Both sub-steps failed — mark explicitly
    if not _ocr_succeeded and not _yolo_succeeded:
        scale_source = "heuristic"
        method = "placeholder"

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
    _log.info(
        "floorplan_cv result: yolo_avg_conf=%.4f rooms=%d scale_source=%s "
        "ocr_dims=%d geometry_confidence=%.4f ocr_ok=%s yolo_ok=%s",
        yolo_avg_conf, len(room_structs), scale_source,
        len(dimensions_raw), geometry_confidence, _ocr_succeeded, _yolo_succeeded,
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
        # Diagnostic sub-step success flags
        "_ocr_succeeded":  _ocr_succeeded,
        "_yolo_succeeded": _yolo_succeeded,
    }

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
    out: dict = {
        "label":   str(raw.get("label") or raw.get("name") or "room"),
        "area_m2": round(area, 2),
    }
    bbox_px = raw.get("bbox_px")
    if bbox_px is not None:
        out["bbox_px"] = bbox_px
    return out


_FT_IN_RE = re.compile(r"(\d+)[\'′’]\s*(\d+(?:\.\d+)?)[\"″”]?")


def _feet_inches_to_m(feet: str, inches: str) -> float:
    return int(feet) * 0.3048 + float(inches) * 0.0254


def _token_to_metres(token: str) -> float | None:
    """Return the metres value implied by *token*, or ``None`` if unparsable."""
    m = re.search(r"([\d.]+)\s*m\b", token, re.IGNORECASE)
    if m:
        try:
            return float(m.group(1))
        except ValueError:
            return None
    fi = _FT_IN_RE.search(token)
    if fi:
        try:
            return _feet_inches_to_m(fi.group(1), fi.group(2))
        except (TypeError, ValueError):
            return None
    return None


def _infer_area_from_dimensions(dimensions: list[str]) -> float:
    """Best-effort: multiply the two largest values (metric or feet/inch) found in OCR text.

    Handles simple cases like '10m x 8m' or "11'3\" x 8'11\"" floor labels.
    Returns 0.0 when fewer than two usable values are found.
    """
    values_m: list[float] = []
    for token in dimensions:
        v = _token_to_metres(token)
        if v is not None:
            values_m.append(v)
    values_m.sort(reverse=True)
    if len(values_m) >= 2:
        return values_m[0] * values_m[1]
    return 0.0


def _sum_room_areas_from_dimensions(dimensions: list[str]) -> float:
    """Parse consecutive W×H pairs (metric or feet/inch) and sum room areas in m²."""
    metres: list[float] = []
    for token in dimensions:
        v = _token_to_metres(token)
        if v is not None:
            metres.append(v)

    total = 0.0
    i = 0
    while i + 1 < len(metres):
        total += metres[i] * metres[i + 1]
        i += 2
    return total


def _match_zones_to_labels(
    yolo_zones: list[dict],
    ocr_labels: list[dict],
    img_w: int,
    img_h: int,
) -> list[dict]:
    """Greedy nearest-centroid matching between YOLO zones and OCR room labels.

    - Threshold = 10 % of image diagonal.
    - Each OCR label can match at most one YOLO zone (greedy, first-wins).
    - Unmatched YOLO zones keep their existing label (typically ``"zone"``).
    """
    if not yolo_zones or not ocr_labels or img_w <= 0 or img_h <= 0:
        return yolo_zones

    diag = math.hypot(img_w, img_h)
    threshold = diag * 0.10

    centroids: list[tuple[float, float] | None] = []
    for label in ocr_labels:
        bbox = label.get("bbox")
        if isinstance(bbox, (list, tuple)) and len(bbox) == 4:
            try:
                x1, y1, x2, y2 = (float(v) for v in bbox)
                centroids.append(((x1 + x2) / 2.0, (y1 + y2) / 2.0))
                continue
            except (TypeError, ValueError):
                pass
        centroids.append(None)

    used: set[int] = set()
    for zone in yolo_zones:
        bbox = zone.get("bbox_px")
        if not isinstance(bbox, (list, tuple)) or len(bbox) != 4:
            continue
        zx, zy = (bbox[0] + bbox[2]) / 2.0, (bbox[1] + bbox[3]) / 2.0

        best: int | None = None
        best_dist = threshold
        for i, c in enumerate(centroids):
            if i in used or c is None:
                continue
            d = math.hypot(zx - c[0], zy - c[1])
            if d < best_dist:
                best, best_dist = i, d

        if best is not None:
            name = ocr_labels[best].get("name")
            if isinstance(name, str) and name.strip():
                zone["label"] = name.strip()
            used.add(best)
    return yolo_zones

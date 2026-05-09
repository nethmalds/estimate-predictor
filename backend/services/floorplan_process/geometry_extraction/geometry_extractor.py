"""Geometry extraction functions called by the floorplan pipeline.

All three public functions delegate to the YOLO detector (yolo_detector.py)
which runs new_best.pt with classes: door(0), window(1), zone(2).

The LRU-cached `detect()` helper in yolo_detector ensures the model
inference runs at most once per unique image path within a pipeline call.
"""
from __future__ import annotations

from pathlib import Path

from services.floorplan_process.geometry_extraction.yolo_detector import (
    detect,
    pixels_to_m2,
)



def get_detection_confidence(image_path: str) -> float:
    """Return the average YOLO detection confidence for *image_path* (0–1).

    Calls the LRU-cached ``detect()`` so there is no extra inference cost
    when called after ``detect_openings`` or ``extract_room_boundaries``.
    Returns 0.0 when no detections were found.
    """
    result = detect(image_path)
    return float(result.get("_yolo_avg_conf", 0.0))


def preprocess_image(image_path: str) -> dict:
    """Validate the image file and return basic metadata."""
    p = Path(image_path)
    if not p.exists():
        raise FileNotFoundError(f"Floor plan image not found: {image_path}")

    size_bytes = p.stat().st_size
    suffix = p.suffix.lower()

    return {
        "image_path": image_path,
        "size_bytes": size_bytes,
        "format": suffix.lstrip("."),
        "method": "yolo_preprocess",
    }


def detect_openings(image_path: str) -> dict:
    """Return door and window counts detected by the YOLO model.

    Returns
    -------
    {"doors": int, "windows": int, "method": str}
    """
    result = detect(image_path)
    doors   = result["doors"]
    windows = result["windows"]

    return {"doors": doors, "windows": windows, "method": "yolo_new_best"}


def extract_room_boundaries(image_path: str) -> dict:
    """Return room list with estimated m² areas detected by the YOLO model.

    Each room entry:
        {"label": str, "area_m2": float}

    The pixel area of each 'zone' detection is converted to m² using the
    pixels_to_m2 helper.  If OCR has already resolved a known total area,
    that value could be passed in as calibration — for now we use the
    heuristic path (200 m² full-image reference).

    Returns
    -------
    {"rooms": list[dict], "method": str}
    """
    result = detect(image_path)
    raw_rooms = result["rooms"]
    img_w     = result["img_w"]
    img_h     = result["img_h"]

    rooms: list[dict] = []
    for i, raw in enumerate(raw_rooms):
        area_m2 = pixels_to_m2(
            area_px=raw["area_px"],
            img_w=img_w,
            img_h=img_h,
            known_area_m2=None,  # no OCR calibration at this stage
        )
        rooms.append({
            "label": raw.get("label", f"zone_{i + 1}"),
            "area_m2": round(area_m2, 2),
        })

    return {"rooms": rooms, "method": "yolo_new_best"}

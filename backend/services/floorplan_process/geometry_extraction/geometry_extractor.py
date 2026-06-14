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
    """Preprocess the floor plan image for downstream OCR/YOLO consumption.

    Steps: greyscale → upscale (if narrower than 640 px) → binarise to black
    walls on a white background. Results are cached by SHA-256 of the input
    bytes so repeated calls on the same image are O(1) disk lookups, sharing
    retention policy with the download cache.
    """
    import hashlib

    from PIL import Image

    from services.floorplan_process.image_cache import _CACHE_DIR

    p = Path(image_path)
    if not p.exists():
        raise FileNotFoundError(f"Floor plan image not found: {image_path}")

    image_bytes = p.read_bytes()
    cache_key   = hashlib.sha256(image_bytes).hexdigest()[:24]

    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    processed_path = _CACHE_DIR / f"{cache_key}_processed{p.suffix or '.png'}"

    img = Image.open(p)
    original_size = img.size

    if not processed_path.exists():
        # 1. Greyscale
        img = img.convert("L")

        # 2. Upscale if too small for YOLO (optimal input ≈ 640 px)
        if img.width < 640:
            scale = 640 / img.width
            img = img.resize(
                (int(img.width * scale), int(img.height * scale)),
                Image.LANCZOS,
            )

        # 3. Binarise — black walls on white background
        img = img.point(lambda px: 0 if px < 200 else 255, "L")
        img.save(processed_path)
        processed_size = img.size
    else:
        with Image.open(processed_path) as cached:
            processed_size = cached.size

    return {
        "image_path":     image_path,
        "processed_path": str(processed_path),
        "original_size":  original_size,
        "processed_size": processed_size,
        "size_bytes":     p.stat().st_size,
        "format":         p.suffix.lstrip("."),
        "method":         "preprocess_binarise",
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
        room_entry: dict = {
            "label": raw.get("label", f"zone_{i + 1}"),
            "area_m2": round(area_m2, 2),
        }
        bbox_px = raw.get("bbox_px")
        if bbox_px is not None:
            room_entry["bbox_px"] = bbox_px
        rooms.append(room_entry)

    return {"rooms": rooms, "method": "yolo_new_best", "img_w": img_w, "img_h": img_h}

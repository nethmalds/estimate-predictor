"""YOLO-based floor plan detector using new_best.pt.

Detected classes (from model.names):
  0: 'door'
  1: 'window'
  2: 'zone'   ← treated as a room/space

Returns a structured geometry dict consumed by the floorplan pipeline.
"""
from __future__ import annotations

import math
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass



_MODEL_PATH = (
    Path(__file__).resolve().parents[3]
    / "infrastructure"
    / "ai"
    / "models"
    / "object_detect"
    / "new_best.pt"
)

# Class ids from new_best.pt (verified via model.names)
_CLS_DOOR   = 0
_CLS_WINDOW = 1
_CLS_ZONE   = 2  # rooms / spaces

# Confidence threshold
_CONF_THRESHOLD = 0.25

# Image size for inference
_IMGSZ = 640

# Assumed real-world scale: 1 pixel ≈ X metres when image is 640 px wide.
# Floor plans vary wildly; we derive a calibration factor from OCR dimensions
# when available.  Without OCR, we fall back to a heuristic that treats the
# total zone area fraction of the image as proportional to built-up area.
_PIXELS_TO_M2_DEFAULT_SCALE = 0.03  # very rough fallback


class YOLOFloorplanDetector:
    """Singleton-style detector — model is loaded once at first use."""

    _instance: "YOLOFloorplanDetector | None" = None

    def __new__(cls) -> "YOLOFloorplanDetector":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._model = None  # type: ignore[attr-defined]
        return cls._instance

    def _load(self) -> None:
        if self._model is not None:
            return
        try:
            import torch
            from ultralytics import YOLO

            device = 0 if torch.cuda.is_available() else "cpu"
            self._model = YOLO(str(_MODEL_PATH))
            self._device = device
        except ImportError as exc:
            raise ImportError(
                "ultralytics and torch are required. "
                "Install with: pip install ultralytics torch"
            ) from exc

    def run(self, image_path: str) -> dict:
        """Run inference on *image_path* and return structured detections.

        Returns
        -------
        dict with keys:
            rooms   : list[dict]  — each has label, area_px, bbox_px
            doors   : int
            windows : int
            raw     : list[dict]  — full detection list for diagnostics
            img_w   : int         — original image width in pixels
            img_h   : int         — original image height in pixels
        """
        self._load()

        results = self._model.predict(  # type: ignore[union-attr]
            source=image_path,
            conf=_CONF_THRESHOLD,
            imgsz=_IMGSZ,
            device=self._device,
            save=False,
            verbose=False,
        )

        if not results:
            return _empty_result()

        result = results[0]
        img_h, img_w = result.orig_shape[:2]

        raw: list[dict] = []
        rooms: list[dict] = []
        doors = 0
        windows = 0

        boxes = result.boxes
        if boxes is None or len(boxes) == 0:
            return _empty_result(img_w=img_w, img_h=img_h)

        for box in boxes:
            cls_id   = int(box.cls[0].item())
            conf     = float(box.conf[0].item())
            x1, y1, x2, y2 = box.xyxy[0].tolist()
            width_px  = x2 - x1
            height_px = y2 - y1
            area_px   = width_px * height_px
            cls_name  = self._model.names.get(cls_id, f"class_{cls_id}")  # type: ignore[union-attr]

            detection = {
                "class": cls_name,
                "class_id": cls_id,
                "conf": round(conf, 3),
                "bbox_px": [round(x1), round(y1), round(x2), round(y2)],
                "area_px": round(area_px),
            }
            raw.append(detection)

            if cls_id == _CLS_DOOR:
                doors += 1
            elif cls_id == _CLS_WINDOW:
                windows += 1
            elif cls_id == _CLS_ZONE:
                rooms.append({
                    "label": "zone",
                    "area_px": area_px,
                    "bbox_px": [round(x1), round(y1), round(x2), round(y2)],
                })

        all_confs = [d["conf"] for d in raw]
        avg_conf = round(sum(all_confs) / len(all_confs), 4) if all_confs else 0.0


        return {
            "rooms": rooms,
            "doors": doors,
            "windows": windows,
            "raw": raw,
            "img_w": img_w,
            "img_h": img_h,
            "_yolo_avg_conf": avg_conf,
            "_yolo_detection_count": len(raw),
        }


def _empty_result(img_w: int = 0, img_h: int = 0) -> dict:
    return {"rooms": [], "doors": 0, "windows": 0, "raw": [], "img_w": img_w, "img_h": img_h}


def pixels_to_m2(area_px: float, img_w: int, img_h: int, known_area_m2: float | None = None) -> float:
    """Convert a pixel area to m² using the best available calibration.

    If *known_area_m2* is provided (derived from OCR dimensions), we use the
    ratio of the total zone pixel area to derive a per-pixel scale factor.
    Otherwise a conservative heuristic is used.
    """
    if area_px <= 0:
        return 0.0
    total_img_px = img_w * img_h
    if total_img_px <= 0:
        return area_px * _PIXELS_TO_M2_DEFAULT_SCALE

    # Fraction of image covered by this detection
    frac = area_px / total_img_px

    if known_area_m2 and known_area_m2 > 0:
        # Scale is: known_area / fraction_of_total_zones
        return frac * known_area_m2
    else:
        # Rough heuristic: treat the whole image as ~200 m²
        return frac * 200.0


# Module-level singleton
_detector = YOLOFloorplanDetector()


@lru_cache(maxsize=16)
def detect(image_path: str) -> dict:
    """Cached detection — avoids running inference twice for the same image."""
    return _detector.run(image_path)

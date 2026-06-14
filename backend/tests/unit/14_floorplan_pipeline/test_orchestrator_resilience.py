"""Unit tests for orchestrator per-step resilience.

Covers:
- Orchestrator continues when YOLO calls raise (returns geometry from OCR)
- Orchestrator continues when OCR raises (returns geometry from YOLO)
- Orchestrator returns empty-but-valid geometry when both fail
- scale_source and method correctly reflect fallback state
- geometry_confidence is always a valid float in [0, 1]
"""
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

_BACKEND_ROOT = Path(__file__).resolve().parents[3]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))


# ── Helpers ──────────────────────────────────────────────────────────────────

def _make_ocr_result(dimensions=None):
    dims = dimensions or []
    return {
        "image_path": "/fake/image.png",
        "text": " ".join(dims),
        "dimensions": dims,
        "dimension_count": len(dims),
    }

def _make_openings_result(doors=0, windows=0):
    return {"doors": doors, "windows": windows, "method": "yolo_new_best"}

def _make_rooms_result(rooms=None):
    rooms = rooms or []
    return {"rooms": rooms, "method": "yolo_new_best"}

def _make_preprocess_result(image_path):
    return {"image_path": image_path, "size_bytes": 1024, "format": "png", "method": "yolo_preprocess"}


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def tmp_image(tmp_path):
    """Create a minimal PNG file so preprocess_image passes its exists() check."""
    img_file = tmp_path / "test_floor.png"
    # Minimal PNG magic bytes
    img_file.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 50)
    return str(img_file)


# ── BE-TC-120: YOLO failure ────────────────────────────────────────────────────

class TestOrchestratorYOLOFailure:
    """When YOLO calls raise, orchestrator must continue using OCR-only signals."""

    def test_continues_when_yolo_raises(self, tmp_image):
        with patch("services.floorplan_process.orchestrator.preprocess_image",
                   return_value=_make_preprocess_result(tmp_image)), \
             patch("services.floorplan_process.orchestrator.extract_floorplan_text_and_dimensions",
                   return_value=_make_ocr_result(["10m", "8m"])), \
             patch("services.floorplan_process.orchestrator.detect_openings",
                   side_effect=RuntimeError("model not found")), \
             patch("services.floorplan_process.orchestrator.extract_room_boundaries",
                   side_effect=RuntimeError("model not found")), \
             patch("services.floorplan_process.orchestrator.get_detection_confidence",
                   side_effect=RuntimeError("model not found")):

            from services.floorplan_process.orchestrator import run_floorplan_pipeline
            result = run_floorplan_pipeline(tmp_image)

        assert isinstance(result, dict), "Must return a dict even when YOLO fails"
        assert result["_yolo_succeeded"] is False
        assert result["_ocr_succeeded"] is True
        assert result["opening_count"] == 0
        assert result["dimensions_raw"] == ["10m", "8m"]

    def test_no_exception_raised_when_yolo_fails(self, tmp_image):
        with patch("services.floorplan_process.orchestrator.preprocess_image",
                   return_value=_make_preprocess_result(tmp_image)), \
             patch("services.floorplan_process.orchestrator.extract_floorplan_text_and_dimensions",
                   return_value=_make_ocr_result([])), \
             patch("services.floorplan_process.orchestrator.detect_openings",
                   side_effect=RuntimeError("YOLO error")), \
             patch("services.floorplan_process.orchestrator.extract_room_boundaries",
                   side_effect=RuntimeError("YOLO error")), \
             patch("services.floorplan_process.orchestrator.get_detection_confidence",
                   side_effect=RuntimeError("YOLO error")):

            from services.floorplan_process.orchestrator import run_floorplan_pipeline
            try:
                run_floorplan_pipeline(tmp_image)
            except Exception as exc:
                pytest.fail(f"run_floorplan_pipeline raised unexpectedly: {exc}")

    def test_geometry_confidence_is_float_when_yolo_fails(self, tmp_image):
        with patch("services.floorplan_process.orchestrator.preprocess_image",
                   return_value=_make_preprocess_result(tmp_image)), \
             patch("services.floorplan_process.orchestrator.extract_floorplan_text_and_dimensions",
                   return_value=_make_ocr_result(["10m", "8m"])), \
             patch("services.floorplan_process.orchestrator.detect_openings",
                   side_effect=RuntimeError("YOLO error")), \
             patch("services.floorplan_process.orchestrator.extract_room_boundaries",
                   side_effect=RuntimeError("YOLO error")), \
             patch("services.floorplan_process.orchestrator.get_detection_confidence",
                   side_effect=RuntimeError("YOLO error")):

            from services.floorplan_process.orchestrator import run_floorplan_pipeline
            result = run_floorplan_pipeline(tmp_image)

        conf = result["geometry_confidence"]
        assert isinstance(conf, float), f"geometry_confidence must be float, got {type(conf)}"
        assert 0.0 <= conf <= 1.0, f"geometry_confidence out of range: {conf}"


# ── BE-TC-121: OCR failure ────────────────────────────────────────────────────

class TestOrchestratorOCRFailure:
    """When OCR raises, orchestrator must continue using YOLO-only signals."""

    def test_continues_when_ocr_raises(self, tmp_image):
        rooms = [{"label": "zone", "area_m2": 50.0}]
        with patch("services.floorplan_process.orchestrator.preprocess_image",
                   return_value=_make_preprocess_result(tmp_image)), \
             patch("services.floorplan_process.orchestrator.extract_floorplan_text_and_dimensions",
                   side_effect=OSError("Tesseract not found")), \
             patch("services.floorplan_process.orchestrator.detect_openings",
                   return_value=_make_openings_result(doors=2, windows=3)), \
             patch("services.floorplan_process.orchestrator.extract_room_boundaries",
                   return_value=_make_rooms_result(rooms=rooms)), \
             patch("services.floorplan_process.orchestrator.get_detection_confidence",
                   return_value=0.45):

            from services.floorplan_process.orchestrator import run_floorplan_pipeline
            result = run_floorplan_pipeline(tmp_image)

        assert isinstance(result, dict)
        assert result["_ocr_succeeded"] is False
        assert result["_yolo_succeeded"] is True
        assert result["dimensions_raw"] == []
        assert result["opening_count"] == 5   # 2 doors + 3 windows

    def test_no_exception_raised_when_ocr_fails(self, tmp_image):
        with patch("services.floorplan_process.orchestrator.preprocess_image",
                   return_value=_make_preprocess_result(tmp_image)), \
             patch("services.floorplan_process.orchestrator.extract_floorplan_text_and_dimensions",
                   side_effect=OSError("Tesseract not found")), \
             patch("services.floorplan_process.orchestrator.detect_openings",
                   return_value=_make_openings_result()), \
             patch("services.floorplan_process.orchestrator.extract_room_boundaries",
                   return_value=_make_rooms_result()), \
             patch("services.floorplan_process.orchestrator.get_detection_confidence",
                   return_value=0.0):

            from services.floorplan_process.orchestrator import run_floorplan_pipeline
            try:
                run_floorplan_pipeline(tmp_image)
            except Exception as exc:
                pytest.fail(f"run_floorplan_pipeline raised unexpectedly: {exc}")


# ── BE-TC-122: Both fail ──────────────────────────────────────────────────────

class TestOrchestratorBothFail:
    """When both OCR and YOLO fail, orchestrator must return empty-but-valid geometry."""

    def test_empty_but_valid_geometry_when_both_fail(self, tmp_image):
        with patch("services.floorplan_process.orchestrator.preprocess_image",
                   return_value=_make_preprocess_result(tmp_image)), \
             patch("services.floorplan_process.orchestrator.extract_floorplan_text_and_dimensions",
                   side_effect=OSError("Tesseract not found")), \
             patch("services.floorplan_process.orchestrator.detect_openings",
                   side_effect=RuntimeError("YOLO failed")), \
             patch("services.floorplan_process.orchestrator.extract_room_boundaries",
                   side_effect=RuntimeError("YOLO failed")), \
             patch("services.floorplan_process.orchestrator.get_detection_confidence",
                   side_effect=RuntimeError("YOLO failed")):

            from services.floorplan_process.orchestrator import run_floorplan_pipeline
            result = run_floorplan_pipeline(tmp_image)

        assert isinstance(result, dict), "Must return a dict even when both fail"
        assert result["total_floor_area_m2"] == 0.0
        assert result["opening_count"] == 0
        assert result["rooms"] == []
        assert result["_ocr_succeeded"] is False
        assert result["_yolo_succeeded"] is False

    def test_scale_source_heuristic_when_both_fail(self, tmp_image):
        with patch("services.floorplan_process.orchestrator.preprocess_image",
                   return_value=_make_preprocess_result(tmp_image)), \
             patch("services.floorplan_process.orchestrator.extract_floorplan_text_and_dimensions",
                   side_effect=OSError("fail")), \
             patch("services.floorplan_process.orchestrator.detect_openings",
                   side_effect=RuntimeError("fail")), \
             patch("services.floorplan_process.orchestrator.extract_room_boundaries",
                   side_effect=RuntimeError("fail")), \
             patch("services.floorplan_process.orchestrator.get_detection_confidence",
                   side_effect=RuntimeError("fail")):

            from services.floorplan_process.orchestrator import run_floorplan_pipeline
            result = run_floorplan_pipeline(tmp_image)

        assert result["scale_source"] == "heuristic"
        assert result["method"] == "placeholder"

    def test_geometry_confidence_non_negative_when_both_fail(self, tmp_image):
        with patch("services.floorplan_process.orchestrator.preprocess_image",
                   return_value=_make_preprocess_result(tmp_image)), \
             patch("services.floorplan_process.orchestrator.extract_floorplan_text_and_dimensions",
                   side_effect=OSError("fail")), \
             patch("services.floorplan_process.orchestrator.detect_openings",
                   side_effect=RuntimeError("fail")), \
             patch("services.floorplan_process.orchestrator.extract_room_boundaries",
                   side_effect=RuntimeError("fail")), \
             patch("services.floorplan_process.orchestrator.get_detection_confidence",
                   side_effect=RuntimeError("fail")):

            from services.floorplan_process.orchestrator import run_floorplan_pipeline
            result = run_floorplan_pipeline(tmp_image)

        assert result["geometry_confidence"] >= 0.0

    def test_no_exception_when_both_fail(self, tmp_image):
        with patch("services.floorplan_process.orchestrator.preprocess_image",
                   return_value=_make_preprocess_result(tmp_image)), \
             patch("services.floorplan_process.orchestrator.extract_floorplan_text_and_dimensions",
                   side_effect=OSError("fail")), \
             patch("services.floorplan_process.orchestrator.detect_openings",
                   side_effect=RuntimeError("fail")), \
             patch("services.floorplan_process.orchestrator.extract_room_boundaries",
                   side_effect=RuntimeError("fail")), \
             patch("services.floorplan_process.orchestrator.get_detection_confidence",
                   side_effect=RuntimeError("fail")):

            from services.floorplan_process.orchestrator import run_floorplan_pipeline
            try:
                run_floorplan_pipeline(tmp_image)
            except Exception as exc:
                pytest.fail(f"run_floorplan_pipeline raised unexpectedly: {exc}")


# ── BE-TC-123: scale_source logic ────────────────────────────────────────────

class TestScaleSourceLogic:
    """scale_source must reflect what signals were available."""

    def test_ocr_confirmed_when_both_succeed_with_rooms_and_dimensions(self, tmp_image):
        rooms = [{"label": "zone", "area_m2": 80.0}]
        with patch("services.floorplan_process.orchestrator.preprocess_image",
                   return_value=_make_preprocess_result(tmp_image)), \
             patch("services.floorplan_process.orchestrator.extract_floorplan_text_and_dimensions",
                   return_value=_make_ocr_result(["10m", "8m"])), \
             patch("services.floorplan_process.orchestrator.detect_openings",
                   return_value=_make_openings_result(doors=1, windows=2)), \
             patch("services.floorplan_process.orchestrator.extract_room_boundaries",
                   return_value=_make_rooms_result(rooms=rooms)), \
             patch("services.floorplan_process.orchestrator.get_detection_confidence",
                   return_value=0.60):

            from services.floorplan_process.orchestrator import run_floorplan_pipeline
            result = run_floorplan_pipeline(tmp_image)

        assert result["scale_source"] == "ocr_confirmed"

    def test_detector_scale_when_yolo_has_rooms_no_ocr_dimensions(self, tmp_image):
        rooms = [{"label": "zone", "area_m2": 60.0}]
        with patch("services.floorplan_process.orchestrator.preprocess_image",
                   return_value=_make_preprocess_result(tmp_image)), \
             patch("services.floorplan_process.orchestrator.extract_floorplan_text_and_dimensions",
                   return_value=_make_ocr_result([])), \
             patch("services.floorplan_process.orchestrator.detect_openings",
                   return_value=_make_openings_result(doors=1)), \
             patch("services.floorplan_process.orchestrator.extract_room_boundaries",
                   return_value=_make_rooms_result(rooms=rooms)), \
             patch("services.floorplan_process.orchestrator.get_detection_confidence",
                   return_value=0.50):

            from services.floorplan_process.orchestrator import run_floorplan_pipeline
            result = run_floorplan_pipeline(tmp_image)

        assert result["scale_source"] == "detector"

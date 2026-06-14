"""Unit tests for YOLO detector graceful degradation.

Covers:
- Model file missing → run() returns empty result, no exception
- _load_error is set (non-empty string) when model cannot load
- Second call after failure does not re-raise
- ultralytics ImportError → graceful empty result
- detect() module-level function returns expected keys on load failure
"""
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

_BACKEND_ROOT = Path(__file__).resolve().parents[3]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

import services.floorplan_process.geometry_extraction.yolo_detector as yolo_mod
from services.floorplan_process.geometry_extraction.yolo_detector import (
    YOLOFloorplanDetector,
    _empty_result,
)


# ── Singleton reset fixture (required before every YOLO test) ────────────────

@pytest.fixture(autouse=True)
def reset_yolo_singleton(monkeypatch, tmp_path):
    """Reset singleton state and lru_cache between tests."""
    monkeypatch.setattr(YOLOFloorplanDetector, "_instance", None)
    fresh = YOLOFloorplanDetector()
    monkeypatch.setattr(yolo_mod, "_detector", fresh)
    yolo_mod.detect.cache_clear()
    yield
    yolo_mod.detect.cache_clear()


# ── BE-TC-110: Model file missing ────────────────────────────────────────────

class TestYOLOModelMissing:
    def test_run_returns_empty_when_model_file_missing(self, monkeypatch, tmp_path):
        """run() must return _empty_result() shape when new_best.pt does not exist."""
        missing_path = tmp_path / "nonexistent.pt"
        monkeypatch.setattr(yolo_mod, "_MODEL_PATH", missing_path)
        # Reset singleton so it picks up the new _MODEL_PATH
        monkeypatch.setattr(YOLOFloorplanDetector, "_instance", None)
        monkeypatch.setattr(yolo_mod, "_detector", YOLOFloorplanDetector())
        yolo_mod.detect.cache_clear()

        detector = YOLOFloorplanDetector()
        result = detector.run("any_image.png")

        assert result["rooms"] == []
        assert result["doors"] == 0
        assert result["windows"] == 0
        assert result["raw"] == []
        assert result["_yolo_avg_conf"] == 0.0

    def test_load_error_is_set_when_model_file_missing(self, monkeypatch, tmp_path):
        """_load_error must be a non-empty string after a failed load."""
        missing_path = tmp_path / "nonexistent.pt"
        monkeypatch.setattr(yolo_mod, "_MODEL_PATH", missing_path)
        monkeypatch.setattr(YOLOFloorplanDetector, "_instance", None)
        monkeypatch.setattr(yolo_mod, "_detector", YOLOFloorplanDetector())
        yolo_mod.detect.cache_clear()

        detector = YOLOFloorplanDetector()
        detector.run("any_image.png")

        assert detector._load_error is not None
        assert isinstance(detector._load_error, str)
        assert len(detector._load_error) > 0

    def test_second_call_does_not_reraise(self, monkeypatch, tmp_path):
        """Second call after load failure must not raise any exception."""
        missing_path = tmp_path / "nonexistent.pt"
        monkeypatch.setattr(yolo_mod, "_MODEL_PATH", missing_path)
        monkeypatch.setattr(YOLOFloorplanDetector, "_instance", None)
        monkeypatch.setattr(yolo_mod, "_detector", YOLOFloorplanDetector())
        yolo_mod.detect.cache_clear()

        detector = YOLOFloorplanDetector()
        # Both calls must succeed without raising
        result1 = detector.run("any_image.png")
        result2 = detector.run("any_image.png")

        assert result1["doors"] == 0
        assert result2["doors"] == 0

    def test_run_no_exception_on_missing_model(self, monkeypatch, tmp_path):
        """run() must not raise any exception when model file is missing."""
        missing_path = tmp_path / "nonexistent.pt"
        monkeypatch.setattr(yolo_mod, "_MODEL_PATH", missing_path)
        monkeypatch.setattr(YOLOFloorplanDetector, "_instance", None)
        monkeypatch.setattr(yolo_mod, "_detector", YOLOFloorplanDetector())
        yolo_mod.detect.cache_clear()

        detector = YOLOFloorplanDetector()
        # Must not raise
        try:
            detector.run("any_image.png")
        except Exception as exc:
            pytest.fail(f"run() raised unexpectedly: {exc}")


# ── BE-TC-111: ImportError for ultralytics ────────────────────────────────────

class TestYOLOImportError:
    def test_run_returns_empty_when_ultralytics_not_importable(self, monkeypatch, tmp_path):
        """When ultralytics cannot be imported, run() must degrade gracefully."""
        # Point to a non-existent model so the load actually tries (not None)
        missing_path = tmp_path / "nonexistent.pt"
        monkeypatch.setattr(yolo_mod, "_MODEL_PATH", missing_path)
        monkeypatch.setattr(YOLOFloorplanDetector, "_instance", None)
        monkeypatch.setattr(yolo_mod, "_detector", YOLOFloorplanDetector())
        yolo_mod.detect.cache_clear()

        original_import = __builtins__.__import__ if hasattr(__builtins__, "__import__") else __import__

        def fake_import(name, *args, **kwargs):
            if name == "ultralytics":
                raise ImportError("ultralytics not installed")
            return original_import(name, *args, **kwargs)

        detector = YOLOFloorplanDetector()
        with patch("builtins.__import__", side_effect=fake_import):
            result = detector.run("any_image.png")

        assert result["rooms"] == []
        assert result["doors"] == 0
        assert result["windows"] == 0

    def test_load_error_set_on_import_error(self, monkeypatch, tmp_path):
        """_load_error must be set when ultralytics import fails."""
        missing_path = tmp_path / "nonexistent.pt"
        monkeypatch.setattr(yolo_mod, "_MODEL_PATH", missing_path)
        monkeypatch.setattr(YOLOFloorplanDetector, "_instance", None)
        monkeypatch.setattr(yolo_mod, "_detector", YOLOFloorplanDetector())
        yolo_mod.detect.cache_clear()

        original_import = __builtins__.__import__ if hasattr(__builtins__, "__import__") else __import__

        def fake_import(name, *args, **kwargs):
            if name == "ultralytics":
                raise ImportError("ultralytics not installed")
            return original_import(name, *args, **kwargs)

        detector = YOLOFloorplanDetector()
        with patch("builtins.__import__", side_effect=fake_import):
            detector.run("any_image.png")

        assert detector._load_error is not None


# ── BE-TC-112: detect() module-level function ─────────────────────────────────

class TestYOLODetectFunction:
    def test_detect_returns_expected_keys_when_load_fails(self, monkeypatch, tmp_path):
        """The module-level detect() must return a dict with all expected keys."""
        missing_path = tmp_path / "nonexistent.pt"
        monkeypatch.setattr(yolo_mod, "_MODEL_PATH", missing_path)
        monkeypatch.setattr(YOLOFloorplanDetector, "_instance", None)
        fresh = YOLOFloorplanDetector()
        monkeypatch.setattr(yolo_mod, "_detector", fresh)
        yolo_mod.detect.cache_clear()

        result = yolo_mod.detect("any_image.png")

        assert "rooms" in result
        assert "doors" in result
        assert "windows" in result
        assert "raw" in result
        assert "_yolo_avg_conf" in result
        assert result["_yolo_avg_conf"] == 0.0
        assert result["doors"] == 0
        assert result["rooms"] == []

    def test_detect_returns_zero_conf_when_load_fails(self, monkeypatch, tmp_path):
        """_yolo_avg_conf must be 0.0 when the model cannot be loaded."""
        missing_path = tmp_path / "nonexistent.pt"
        monkeypatch.setattr(yolo_mod, "_MODEL_PATH", missing_path)
        monkeypatch.setattr(YOLOFloorplanDetector, "_instance", None)
        fresh = YOLOFloorplanDetector()
        monkeypatch.setattr(yolo_mod, "_detector", fresh)
        yolo_mod.detect.cache_clear()

        result = yolo_mod.detect("any_image.png")
        assert result["_yolo_avg_conf"] == 0.0


# ── BE-TC-113: _empty_result shape ───────────────────────────────────────────

class TestEmptyResultShape:
    def test_empty_result_has_all_expected_keys(self):
        """_empty_result() must contain all keys consumed by the orchestrator."""
        result = _empty_result()
        required_keys = {"rooms", "doors", "windows", "raw", "img_w", "img_h",
                         "_yolo_avg_conf", "_yolo_detection_count"}
        assert required_keys.issubset(result.keys()), (
            f"Missing keys: {required_keys - result.keys()}"
        )

    def test_empty_result_zero_counts(self):
        result = _empty_result()
        assert result["doors"] == 0
        assert result["windows"] == 0
        assert result["_yolo_avg_conf"] == 0.0
        assert result["_yolo_detection_count"] == 0

    def test_empty_result_custom_dimensions(self):
        result = _empty_result(img_w=640, img_h=480)
        assert result["img_w"] == 640
        assert result["img_h"] == 480

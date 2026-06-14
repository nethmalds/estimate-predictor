"""Unit tests for the vision-API OCR fallback in ocr.py.

CRITICAL: every test mocks `_call_llm_vision`. None of these tests must hit
the real LLM endpoint.

Covers:
- Vision is invoked when Tesseract raises TesseractNotFoundError
- Vision responses are cached on disk by SHA-256 of the image bytes
- Timeout returns _ocr_skip_result with reason "vision_timeout"
- Circuit breaker opens after 5 consecutive failures
- JSON response parsed → dimensions and labels both extracted
- Non-JSON response falls back to running the regex on raw text
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

_BACKEND_ROOT = Path(__file__).resolve().parents[3]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))


def _make_tiny_png(tmp_path: Path, name: str = "v.png") -> Path:
    from PIL import Image  # type: ignore[import]
    img = Image.new("L", (16, 16), color=180)
    p = tmp_path / name
    img.save(p, format="PNG")
    return p


@pytest.fixture(autouse=True)
def _reset_circuit_state(tmp_path, monkeypatch):
    """Reset module-level circuit state and redirect cache dir to tmp."""
    import services.floorplan_process.geometry_extraction.ocr as ocr_mod
    monkeypatch.setattr(ocr_mod, "_VISION_CACHE_DIR", tmp_path / "vision_cache")
    ocr_mod._vision_failure_timestamps.clear()
    ocr_mod._circuit_open_until = 0.0
    yield
    ocr_mod._vision_failure_timestamps.clear()
    ocr_mod._circuit_open_until = 0.0


class _TesseractNotFound(Exception):
    """Stand-in for pytesseract.TesseractNotFoundError."""


def _patch_tesseract_missing():
    """Patch pytesseract.image_to_string + TesseractNotFoundError class together."""
    import pytesseract  # type: ignore[import]

    patches = [
        patch.object(pytesseract, "image_to_string",
                     side_effect=pytesseract.TesseractNotFoundError()),
    ]
    return patches


class TestVisionCalledWhenTesseractMissing:
    def test_vision_invoked_and_dimensions_populated(self, tmp_path):
        from services.floorplan_process.geometry_extraction import ocr as ocr_mod

        img = _make_tiny_png(tmp_path)
        vision_text = json.dumps([
            {"name": "Bedroom 1", "dimension_label": "11'3\" x 8'11\"",
             "bbox": [10, 10, 50, 30]},
            {"name": "Kitchen", "dimension_label": "12'0\" x 10'0\"",
             "bbox": [60, 10, 110, 30]},
        ])
        with _patch_tesseract_missing()[0], \
             patch.object(ocr_mod, "_call_llm_vision", return_value=vision_text) as mock_call:
            result = ocr_mod.extract_floorplan_text_and_dimensions(str(img))

        assert mock_call.called, "Vision API must be invoked when Tesseract missing"
        assert result["dimensions"], "dimensions must be populated from vision JSON"
        assert any("11" in d for d in result["dimensions"])
        assert {l["name"] for l in result["ocr_labels"]} == {"Bedroom 1", "Kitchen"}
        assert result["vision_source"] is True


class TestVisionResponseCached:
    def test_second_call_hits_disk_cache(self, tmp_path):
        from services.floorplan_process.geometry_extraction import ocr as ocr_mod
        img = _make_tiny_png(tmp_path)
        vision_text = json.dumps([
            {"name": "Hall", "dimension_label": "5m x 3m", "bbox": [0, 0, 10, 10]}
        ])
        with _patch_tesseract_missing()[0], \
             patch.object(ocr_mod, "_call_llm_vision", return_value=vision_text) as mock_call:
            first = ocr_mod.extract_floorplan_text_and_dimensions(str(img))
            second = ocr_mod.extract_floorplan_text_and_dimensions(str(img))

        assert mock_call.call_count == 1, (
            f"Vision should be called once; got {mock_call.call_count}"
        )
        assert second.get("vision_cache_hit") is True
        assert first["dimensions"] == second["dimensions"]


class TestVisionTimeout:
    def test_timeout_returns_skip_result(self, tmp_path):
        from services.floorplan_process.geometry_extraction import ocr as ocr_mod
        img = _make_tiny_png(tmp_path)

        with _patch_tesseract_missing()[0], \
             patch.object(ocr_mod, "_extract_dimensions_via_vision",
                          side_effect=TimeoutError("slow")):
            result = ocr_mod.extract_floorplan_text_and_dimensions(str(img))

        assert result["ocr_skipped"] is True
        assert result["ocr_skip_reason"] == "vision_timeout"


class TestCircuitBreaker:
    def test_opens_after_threshold(self, tmp_path):
        from services.floorplan_process.geometry_extraction import ocr as ocr_mod
        img = _make_tiny_png(tmp_path)

        # 5 consecutive failures
        with _patch_tesseract_missing()[0], \
             patch.object(ocr_mod, "_extract_dimensions_via_vision",
                          side_effect=RuntimeError("upstream down")):
            for _ in range(ocr_mod._CIRCUIT_THRESHOLD):
                ocr_mod.extract_floorplan_text_and_dimensions(str(img))

        # 6th call should short-circuit even without invoking vision
        with _patch_tesseract_missing()[0], \
             patch.object(ocr_mod, "_extract_dimensions_via_vision") as mock_vision:
            result = ocr_mod.extract_floorplan_text_and_dimensions(str(img))

        assert result["ocr_skipped"] is True
        assert result["ocr_skip_reason"] == "vision_circuit_open"
        assert mock_vision.called is False, "Vision must not be invoked while circuit open"


class TestNonJSONFallback:
    def test_plain_text_response_yields_dimensions_via_regex(self, tmp_path):
        from services.floorplan_process.geometry_extraction import ocr as ocr_mod
        img = _make_tiny_png(tmp_path)
        # No JSON, just prose with dim tokens
        plain = "Bedroom 1: 11'3\" x 8'11\". Kitchen 12'0\" x 10'0\"."

        with _patch_tesseract_missing()[0], \
             patch.object(ocr_mod, "_call_llm_vision", return_value=plain):
            result = ocr_mod.extract_floorplan_text_and_dimensions(str(img))

        assert result["dimensions"], "Regex fallback must still recover dimensions"
        assert result["ocr_labels"] == []

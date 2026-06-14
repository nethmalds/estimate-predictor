"""Unit tests for the hash-keyed preprocess cache in geometry_extractor.preprocess_image.

Covers:
- Deterministic processed_path for identical image bytes
- Cache hit avoids re-running the PIL binarisation pass
- Orchestrator's exception path falls back to image_path
"""
from __future__ import annotations

import io
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

_BACKEND_ROOT = Path(__file__).resolve().parents[3]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))


def _make_tiny_png(tmp_path: Path, name: str = "tiny.png") -> Path:
    """Write a real 8×8 grayscale PNG so PIL can open it."""
    from PIL import Image  # type: ignore[import]

    img = Image.new("L", (8, 8), color=128)
    out = tmp_path / name
    img.save(out, format="PNG")
    return out


class TestProcessedPathDeterministic:
    def test_same_bytes_produce_same_processed_path(self, tmp_path):
        img_a = _make_tiny_png(tmp_path, "a.png")
        # Identical bytes copied to a different filename
        img_b = tmp_path / "b.png"
        img_b.write_bytes(img_a.read_bytes())

        from services.floorplan_process.geometry_extraction.geometry_extractor import (
            preprocess_image,
        )
        out_a = preprocess_image(str(img_a))
        out_b = preprocess_image(str(img_b))

        assert out_a["processed_path"] == out_b["processed_path"]
        assert Path(out_a["processed_path"]).exists()

    def test_different_bytes_produce_different_processed_paths(self, tmp_path):
        img_a = _make_tiny_png(tmp_path, "a.png")
        from PIL import Image  # type: ignore[import]

        img_b_path = tmp_path / "b.png"
        Image.new("L", (16, 16), color=200).save(img_b_path, format="PNG")

        from services.floorplan_process.geometry_extraction.geometry_extractor import (
            preprocess_image,
        )
        out_a = preprocess_image(str(img_a))
        out_b = preprocess_image(str(img_b_path))

        assert out_a["processed_path"] != out_b["processed_path"]


class TestCacheHit:
    def test_cache_hit_skips_pil_point(self, tmp_path):
        img = _make_tiny_png(tmp_path, "warm.png")

        from services.floorplan_process.geometry_extraction.geometry_extractor import (
            preprocess_image,
        )
        # Prime the cache
        first = preprocess_image(str(img))
        assert Path(first["processed_path"]).exists()

        # Second call should NOT call .point() on a new image
        from PIL import Image as PILImage  # type: ignore[import]

        original_point = PILImage.Image.point
        call_counter = {"n": 0}

        def counted_point(self, *args, **kwargs):
            call_counter["n"] += 1
            return original_point(self, *args, **kwargs)

        with patch.object(PILImage.Image, "point", counted_point):
            second = preprocess_image(str(img))

        assert second["processed_path"] == first["processed_path"]
        assert call_counter["n"] == 0, "PIL.Image.point should not be called on cache hit"


class TestOrchestratorPreprocessFallback:
    def test_fallback_processed_path_is_original_when_preprocess_fails(self, tmp_path):
        img = _make_tiny_png(tmp_path, "orch.png")

        from services.floorplan_process import orchestrator as orch

        with patch.object(orch, "preprocess_image", side_effect=RuntimeError("boom")), \
             patch.object(orch, "extract_floorplan_text_and_dimensions",
                          return_value={"image_path": str(img), "text": "",
                                        "dimensions": [], "dimension_count": 0}), \
             patch.object(orch, "detect_openings",
                          return_value={"doors": 0, "windows": 0, "method": "x"}), \
             patch.object(orch, "extract_room_boundaries",
                          return_value={"rooms": [], "method": "x", "img_w": 0, "img_h": 0}), \
             patch.object(orch, "get_detection_confidence", return_value=0.0):

            result = orch.run_floorplan_pipeline(str(img))

        # The orchestrator should have built a fallback dict whose processed_path
        # points back at the original image rather than being absent.
        assert result["_preprocess"]["processed_path"] == str(img)
        assert result["_preprocess"]["method"] == "failed"

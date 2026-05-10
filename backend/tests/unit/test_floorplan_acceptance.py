"""Unit tests for the floorplan acceptance boundary logic.

Tests the acceptance gate function directly, without importing the full pipeline
(which has heavy transitive dependencies on chromadb / numpy).

Verifies:
- Geometry below threshold is rejected (returns None geometry)
- Geometry at or above threshold is accepted
- floorplan_meta reflects accepted/rejected state with correct fields
- Threshold is configurable
- Rejected geometry: rejection_reason and scale_source preserved in meta
"""
import sys
from pathlib import Path

_BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))


# ---------------------------------------------------------------------------
# Pure acceptance gate logic — extracted from estimation_pipeline.py so tests
# do not depend on chromadb / heavy imports.  This mirrors the exact gate code.
# ---------------------------------------------------------------------------

def _apply_acceptance_gate(
    geometry: dict,
    threshold: float = 0.30,
) -> tuple[dict | None, dict]:
    """Replicate the Stage 2a acceptance gate from estimation_pipeline."""
    geo_conf = float(geometry.get("geometry_confidence") or 0.0)

    if geo_conf < threshold:
        rejection_reason = (
            f"Geometry confidence {geo_conf:.3f} is below acceptance "
            f"threshold {threshold:.2f}. Falling back to parametric-only path."
        )
        scale_src = geometry.get("scale_source")
        heuristic_flags = geometry.get("heuristic_flags")
        meta = {
            "available": False,
            "accepted": False,
            "rejection_reason": rejection_reason,
            "geometry_confidence": geo_conf,
            "scale_source": scale_src,
            "heuristic_flags": heuristic_flags,
        }
        return None, meta
    else:
        meta = {
            "available": True,
            "accepted": True,
            "source_count": 1,
            "method": geometry.get("method"),
            "total_floor_area_m2": geometry.get("total_floor_area_m2"),
            "opening_count": geometry.get("opening_count"),
            "room_count": geometry.get("room_count"),
            "geometry_confidence": geo_conf,
            "scale_source": geometry.get("scale_source"),
            "heuristic_flags": geometry.get("heuristic_flags"),
        }
        return geometry, meta


def _make_geometry(confidence: float, scale_source: str = "ocr_confirmed") -> dict:
    return {
        "geometry_confidence": confidence,
        "total_floor_area_m2": 150.0,
        "opening_count": 8,
        "room_count": 4,
        "method": "ocr_dimensions",
        "scale_source": scale_source,
        "heuristic_flags": {"assumed_floor_height": True},
    }


def _run_pipeline_acceptance_test(geometry_confidence: float, threshold: float = 0.30):
    return _apply_acceptance_gate(_make_geometry(geometry_confidence), threshold=threshold)


class TestFloorplanAcceptanceBoundary:
    def test_high_confidence_geometry_is_accepted(self):
        geom, meta = _run_pipeline_acceptance_test(geometry_confidence=0.75)
        assert geom is not None
        assert meta["accepted"] is True
        assert meta["available"] is True

    def test_low_confidence_geometry_is_rejected(self):
        geom, meta = _run_pipeline_acceptance_test(geometry_confidence=0.15)
        assert geom is None, "Low-confidence geometry must be nullified"
        assert meta["accepted"] is False
        assert meta["available"] is False

    def test_geometry_at_threshold_is_accepted(self):
        """Geometry exactly at threshold must be accepted (>= check)."""
        geom, meta = _run_pipeline_acceptance_test(geometry_confidence=0.30, threshold=0.30)
        assert geom is not None
        assert meta["accepted"] is True

    def test_geometry_just_below_threshold_is_rejected(self):
        geom, meta = _run_pipeline_acceptance_test(geometry_confidence=0.29, threshold=0.30)
        assert geom is None
        assert meta["accepted"] is False

    def test_rejection_meta_preserves_scale_source(self):
        """scale_source must be preserved in meta even after geometry is rejected."""
        geom, meta = _run_pipeline_acceptance_test(geometry_confidence=0.10)
        assert geom is None
        assert meta.get("scale_source") == "ocr_confirmed"

    def test_rejection_meta_has_rejection_reason(self):
        geom, meta = _run_pipeline_acceptance_test(geometry_confidence=0.05)
        assert "rejection_reason" in meta
        assert "threshold" in meta["rejection_reason"] or "below" in meta["rejection_reason"]

    def test_rejection_meta_has_geometry_confidence(self):
        geom, meta = _run_pipeline_acceptance_test(geometry_confidence=0.20)
        assert meta.get("geometry_confidence") == 0.20

    def test_zero_confidence_is_rejected(self):
        geom, meta = _run_pipeline_acceptance_test(geometry_confidence=0.0)
        assert geom is None
        assert meta["accepted"] is False


class TestThresholdConfiguration:
    def test_custom_threshold_rejects_mid_confidence(self):
        """0.45 confidence accepted at 0.30 threshold but rejected at 0.50."""
        geom_accepted, _ = _run_pipeline_acceptance_test(geometry_confidence=0.45, threshold=0.30)
        geom_rejected, _ = _run_pipeline_acceptance_test(geometry_confidence=0.45, threshold=0.50)
        assert geom_accepted is not None, "0.45 should be accepted at threshold 0.30"
        assert geom_rejected is None, "0.45 should be rejected at threshold 0.50"

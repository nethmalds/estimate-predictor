"""Unit tests for compute_geometry_confidence in floorplan_process/confidence_scorer.py.

Covers:
- BE-TC-081: geometry confidence drops when scale_source is 'heuristic' vs 'ocr_confirmed'
- BE-TC-082: confidence score is bounded between 0.0 and 1.0
"""
import sys
from pathlib import Path

import pytest

_BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from services.floorplan_process.confidence_scorer import compute_geometry_confidence  # noqa: E402


# ── BE-TC-081: heuristic scale_source produces lower score than ocr_confirmed ─

class TestScaleSourceImpact:
    def test_heuristic_lower_than_ocr_confirmed(self):
        heuristic = compute_geometry_confidence(
            ocr_confidence=1.0,
            detector_confidence=0.8,
            scale_source="heuristic",
            coverage_confidence=0.9,
        )
        ocr_confirmed = compute_geometry_confidence(
            ocr_confidence=1.0,
            detector_confidence=0.8,
            scale_source="ocr_confirmed",
            coverage_confidence=0.9,
        )
        assert heuristic < ocr_confirmed, (
            f"heuristic score {heuristic} should be less than ocr_confirmed {ocr_confirmed}"
        )

    def test_scale_source_ranking_from_best_to_worst(self):
        kwargs = dict(ocr_confidence=0.8, detector_confidence=0.7, coverage_confidence=0.8)
        scores = {
            src: compute_geometry_confidence(scale_source=src, **kwargs)
            for src in ("ocr_confirmed", "ocr_dimensions", "detector", "area_inferred", "heuristic")
        }
        # Each source should produce a strictly lower-or-equal score as quality degrades
        assert scores["ocr_confirmed"] >= scores["ocr_dimensions"]
        assert scores["ocr_dimensions"] >= scores["detector"]
        assert scores["detector"] >= scores["area_inferred"]
        assert scores["area_inferred"] >= scores["heuristic"]

    def test_unknown_scale_source_treated_as_heuristic(self):
        known_heuristic = compute_geometry_confidence(
            ocr_confidence=0.5,
            detector_confidence=0.5,
            scale_source="heuristic",
            coverage_confidence=0.5,
        )
        unknown = compute_geometry_confidence(
            ocr_confidence=0.5,
            detector_confidence=0.5,
            scale_source="totally_unknown",
            coverage_confidence=0.5,
        )
        # Both should use the lowest scale score (0.20)
        assert unknown == pytest.approx(known_heuristic, abs=0.001)


# ── BE-TC-082: confidence score bounded between 0.0 and 1.0 ──────────────────

class TestConfidenceBounds:
    def test_max_inputs_do_not_exceed_1_0(self):
        score = compute_geometry_confidence(
            ocr_confidence=1.0,
            detector_confidence=1.0,
            scale_source="ocr_confirmed",
            coverage_confidence=1.0,
            heuristic_flags={},
        )
        assert 0.0 <= score <= 1.0

    def test_min_inputs_do_not_go_below_0_0(self):
        score = compute_geometry_confidence(
            ocr_confidence=0.0,
            detector_confidence=0.0,
            scale_source="heuristic",
            coverage_confidence=0.0,
            heuristic_flags={
                "assumed_floor_height": True,
                "inferred_internal_walls": True,
                "derived_from_area_only": True,
                "missing_scale_confirmation": True,
            },
        )
        assert score >= 0.0

    def test_score_is_float(self):
        score = compute_geometry_confidence(
            ocr_confidence=0.7,
            detector_confidence=0.6,
            scale_source="ocr_dimensions",
            coverage_confidence=0.8,
        )
        assert isinstance(score, float)

    def test_all_heuristic_flags_true_reduces_score(self):
        no_flags = compute_geometry_confidence(
            ocr_confidence=0.8,
            detector_confidence=0.7,
            scale_source="ocr_confirmed",
            coverage_confidence=0.9,
            heuristic_flags={},
        )
        all_flags = compute_geometry_confidence(
            ocr_confidence=0.8,
            detector_confidence=0.7,
            scale_source="ocr_confirmed",
            coverage_confidence=0.9,
            heuristic_flags={
                "assumed_floor_height": True,
                "inferred_internal_walls": True,
                "derived_from_area_only": True,
                "missing_scale_confirmation": True,
            },
        )
        assert all_flags < no_flags


class TestHeuristicFlagPenalty:
    def test_no_heuristic_flags_no_penalty(self):
        with_no_flags = compute_geometry_confidence(
            ocr_confidence=0.9,
            detector_confidence=0.8,
            scale_source="ocr_confirmed",
            coverage_confidence=0.9,
            heuristic_flags={"assumed_floor_height": False},
        )
        with_empty_flags = compute_geometry_confidence(
            ocr_confidence=0.9,
            detector_confidence=0.8,
            scale_source="ocr_confirmed",
            coverage_confidence=0.9,
            heuristic_flags={},
        )
        assert with_no_flags == pytest.approx(with_empty_flags, abs=0.001)

    def test_partial_heuristic_flags_partial_penalty(self):
        half_flags = compute_geometry_confidence(
            ocr_confidence=0.8,
            detector_confidence=0.7,
            scale_source="ocr_confirmed",
            coverage_confidence=0.8,
            heuristic_flags={"a": True, "b": False},  # 50% heuristic
        )
        full_flags = compute_geometry_confidence(
            ocr_confidence=0.8,
            detector_confidence=0.7,
            scale_source="ocr_confirmed",
            coverage_confidence=0.8,
            heuristic_flags={"a": True, "b": True},  # 100% heuristic
        )
        assert full_flags < half_flags

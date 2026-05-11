"""Unit tests for arithmetic-mean quantity reconciliation in confidence_scoring.py.

Verifies:
- Continuous units: fuse_candidates uses arithmetic mean (not weighted mean)
- Discrete units: winner-takes-all, ceil applied
- Single valid source: uses that source directly
- Zero/negative candidates are excluded from fusion
- Disagreement score is computed when 2+ candidates present
"""
import sys
from pathlib import Path

_BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from services.quantity_gen_process.confidence_scoring import fuse_candidates  # noqa: E402


class TestArithmeticMeanContinuous:
    """Continuous units must use arithmetic mean, not weighted mean."""

    def test_two_equal_candidates_returns_mean(self):
        candidates = [(100.0, "geometry", False), (200.0, "parametric", False)]
        qty, conf, src, meta = fuse_candidates(candidates, geo_conf=0.8, unit="m²")
        assert qty == 150.0, f"Expected arithmetic mean 150.0, got {qty}"

    def test_two_unequal_candidates_returns_mean(self):
        candidates = [(50.0, "geometry", False), (150.0, "parametric", False)]
        qty, conf, src, meta = fuse_candidates(candidates, geo_conf=0.7, unit="m²")
        assert qty == 100.0, f"Expected arithmetic mean 100.0, got {qty}"

    def test_three_candidates_returns_mean(self):
        candidates = [
            (30.0, "geometry", False),
            (60.0, "parametric", False),
            (90.0, "quantity_predictor", True),
        ]
        qty, conf, src, meta = fuse_candidates(candidates, geo_conf=0.6, unit="m³")
        assert qty == 60.0, f"Expected arithmetic mean 60.0, got {qty}"

    def test_single_valid_candidate_returns_that_value(self):
        candidates = [(75.5, "parametric", False)]
        qty, conf, src, meta = fuse_candidates(candidates, geo_conf=0.0, unit="m²")
        assert qty == 75.5

    def test_weighted_mean_would_differ_from_arithmetic(self):
        """Guard: result must equal arithmetic mean, not weighted mean.

        geometry weight ≈ 0.80, parametric weight = 0.60.
        Weighted mean of (10, 100): (0.80×10 + 0.60×100) / (0.80+0.60) = 51.43
        Arithmetic mean: (10 + 100) / 2 = 55.0
        """
        candidates = [(10.0, "geometry", False), (100.0, "parametric", False)]
        qty, conf, src, meta = fuse_candidates(candidates, geo_conf=0.8, unit="m²")
        assert qty == 55.0, f"Expected arithmetic mean 55.0, not weighted mean. Got {qty}"

    def test_zero_quantity_excluded(self):
        candidates = [(0.0, "geometry", False), (80.0, "parametric", False)]
        qty, conf, src, meta = fuse_candidates(candidates, geo_conf=0.5, unit="m²")
        # Only the 80.0 candidate is valid
        assert qty == 80.0

    def test_negative_quantity_excluded(self):
        candidates = [(-5.0, "geometry", False), (40.0, "parametric", False)]
        qty, conf, src, meta = fuse_candidates(candidates, geo_conf=0.5, unit="m²")
        assert qty == 40.0

    def test_disagreement_score_set_when_two_candidates(self):
        candidates = [(10.0, "geometry", False), (90.0, "parametric", False)]
        qty, conf, src, meta = fuse_candidates(candidates, geo_conf=0.5, unit="m²")
        # δ = (90-10) / mean(10,90) = 80/50 = 1.6
        for m in meta:
            assert "disagreement_score" in m["diagnostics"]


class TestDiscreteWinnerTakesAll:
    """Discrete units (Nr, Item) must use winner-takes-all and ceil."""

    def test_discrete_nr_returns_ceil_of_winner(self):
        # geometry weight > parametric weight, geometry wins
        candidates = [(2.3, "geometry", False), (4.0, "parametric", False)]
        qty, conf, src, meta = fuse_candidates(candidates, geo_conf=0.9, unit="Nr")
        assert qty == 3.0, f"Expected ceil(2.3)=3, got {qty}"  # geometry wins with higher weight

    def test_discrete_item_winner(self):
        candidates = [(1.0, "parametric", False)]
        qty, conf, src, meta = fuse_candidates(candidates, geo_conf=0.0, unit="Item")
        assert qty == 1.0

    def test_discrete_ceil_applied(self):
        candidates = [(1.1, "parametric", False), (1.9, "geometry", False)]
        qty, conf, src, meta = fuse_candidates(candidates, geo_conf=0.95, unit="Nr")
        # geometry wins (higher conf), ceil(1.9) = 2
        assert qty == 2.0

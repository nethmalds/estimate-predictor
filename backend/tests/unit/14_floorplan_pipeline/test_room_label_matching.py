"""Unit tests for centroid-based room-label matching between YOLO zones and OCR labels.

Covers:
- Labels within the 10% diagonal threshold are assigned to the nearest zone
- Labels outside the threshold are dropped silently
- Greedy: when two labels are close to the same zone, the first wins
- Imperial dimension parsing utilities used by orchestrator
- Room-area summation across consecutive W×H pairs
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_BACKEND_ROOT = Path(__file__).resolve().parents[3]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))


class TestCentroidMatching:
    def test_label_within_threshold_matches_zone(self):
        from services.floorplan_process.orchestrator import _match_zones_to_labels
        # Two zones, two labels — labels sitting inside each zone
        zones = [
            {"label": "zone", "bbox_px": [0, 0, 100, 100]},
            {"label": "zone", "bbox_px": [200, 0, 300, 100]},
        ]
        labels = [
            {"name": "Bedroom", "bbox": [40, 40, 60, 60]},      # centre 50,50
            {"name": "Kitchen", "bbox": [240, 40, 260, 60]},    # centre 250,50
        ]
        out = _match_zones_to_labels(zones, labels, img_w=400, img_h=400)
        assert out[0]["label"] == "Bedroom"
        assert out[1]["label"] == "Kitchen"

    def test_label_outside_threshold_dropped(self):
        from services.floorplan_process.orchestrator import _match_zones_to_labels
        zones = [{"label": "zone", "bbox_px": [0, 0, 100, 100]}]
        # Image diagonal ≈ 1414 ⇒ threshold ≈ 141; label at 800,800 is far away
        labels = [{"name": "FarAway", "bbox": [780, 780, 820, 820]}]
        out = _match_zones_to_labels(zones, labels, img_w=1000, img_h=1000)
        assert out[0]["label"] == "zone"

    def test_more_zones_than_labels_keeps_extras(self):
        from services.floorplan_process.orchestrator import _match_zones_to_labels
        zones = [
            {"label": "zone", "bbox_px": [0, 0, 100, 100]},
            {"label": "zone", "bbox_px": [200, 0, 300, 100]},
            {"label": "zone", "bbox_px": [400, 0, 500, 100]},
        ]
        labels = [{"name": "OnlyOne", "bbox": [40, 40, 60, 60]}]
        out = _match_zones_to_labels(zones, labels, img_w=600, img_h=600)
        assert out[0]["label"] == "OnlyOne"
        assert out[1]["label"] == "zone"
        assert out[2]["label"] == "zone"

    def test_greedy_first_wins_when_two_labels_target_same_zone(self):
        from services.floorplan_process.orchestrator import _match_zones_to_labels
        zones = [
            {"label": "zone", "bbox_px": [0, 0, 100, 100]},
            {"label": "zone", "bbox_px": [200, 200, 300, 300]},
        ]
        # Both labels near zone[0]; second zone has none.
        labels = [
            {"name": "First",  "bbox": [40, 40, 60, 60]},
            {"name": "Second", "bbox": [45, 45, 55, 55]},
        ]
        out = _match_zones_to_labels(zones, labels, img_w=400, img_h=400)
        assert out[0]["label"] == "First"
        # Second label gets matched to zone[1] only if within threshold; else stays.
        # In a 400×400 image, diag≈566, threshold≈56; (50,50)→(250,250) dist≈283 → no match
        assert out[1]["label"] == "zone"


class TestImperialDimensionParsing:
    def test_feet_inches_parsed_into_metres(self):
        from services.floorplan_process.orchestrator import _infer_area_from_dimensions
        # 11'3" x 8'11"  ≈ 3.4290 m × 2.7178 m ≈ 9.32 m²
        area = _infer_area_from_dimensions(["11'3\"", "8'11\""])
        assert 8.5 < area < 10.5, f"got {area}"

    def test_metric_and_imperial_mixed(self):
        from services.floorplan_process.orchestrator import _infer_area_from_dimensions
        area = _infer_area_from_dimensions(["10m", "8'0\""])
        # Two largest metres: 10.0 and (8*0.3048=2.4384) → 24.384 m²
        assert 23.0 < area < 26.0, f"got {area}"

    def test_returns_zero_when_unparseable(self):
        from services.floorplan_process.orchestrator import _infer_area_from_dimensions
        assert _infer_area_from_dimensions(["abc", "xyz"]) == 0.0


class TestRoomAreaSummation:
    def test_eight_room_imperial_labels_sum_correctly(self):
        from services.floorplan_process.orchestrator import _sum_room_areas_from_dimensions
        # 4 rooms × (10' × 8') → each ≈ 7.43 m² → total ≈ 29.7 m²
        dims = ["10'0\"", "8'0\""] * 4
        total = _sum_room_areas_from_dimensions(dims)
        per_room = (10 * 0.3048) * (8 * 0.3048)
        assert abs(total - 4 * per_room) < 0.5

    def test_all_metric_pairs(self):
        from services.floorplan_process.orchestrator import _sum_room_areas_from_dimensions
        total = _sum_room_areas_from_dimensions(["3m", "4m", "5m", "6m"])
        # 3*4 + 5*6 = 12 + 30 = 42
        assert total == pytest.approx(42.0)

    def test_odd_count_drops_trailing_token(self):
        from services.floorplan_process.orchestrator import _sum_room_areas_from_dimensions
        total = _sum_room_areas_from_dimensions(["3m", "4m", "5m"])
        assert total == pytest.approx(12.0)

    def test_no_parseable_tokens_returns_zero(self):
        from services.floorplan_process.orchestrator import _sum_room_areas_from_dimensions
        assert _sum_room_areas_from_dimensions(["abc", "xyz"]) == 0.0

"""Unit tests for _merge_floorplan_geometries in estimation_pipeline.py."""
import sys
from pathlib import Path

_BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from application.pipelines.estimation_pipeline import _merge_floorplan_geometries  # noqa: E402


def _geom(area=100.0, perimeter=40.0, walls=55.0, openings=4, rooms=3,
          confidence=0.8, scale="ocr_confirmed", inferred=False, flags=None):
    return {
        "total_floor_area_m2": area,
        "perimeter_m": perimeter,
        "wall_length_m": walls,
        "opening_count": openings,
        "room_count": rooms,
        "rooms": [{"label": "room", "area_m2": area / rooms}] * rooms,
        "geometry_confidence": confidence,
        "scale_source": scale,
        "inferred_area_flag": inferred,
        "heuristic_flags": flags or {
            "derived_from_area_only": False,
            "assumed_floor_height": True,
            "inferred_internal_walls": False,
            "missing_scale_confirmation": False,
        },
    }


class TestMergeFloorplanGeometries:
    def test_empty_list_returns_empty_dict(self):
        assert _merge_floorplan_geometries([]) == {}

    def test_single_geometry_returned_unchanged(self):
        g = _geom()
        result = _merge_floorplan_geometries([g])
        assert result is g

    def test_two_geometries_areas_summed(self):
        g1 = _geom(area=100.0)
        g2 = _geom(area=80.0)
        result = _merge_floorplan_geometries([g1, g2])
        assert result["total_floor_area_m2"] == 180.0

    def test_two_geometries_openings_summed(self):
        g1 = _geom(openings=5)
        g2 = _geom(openings=3)
        result = _merge_floorplan_geometries([g1, g2])
        assert result["opening_count"] == 8

    def test_two_geometries_rooms_concatenated(self):
        g1 = _geom(rooms=3)
        g2 = _geom(rooms=4)
        result = _merge_floorplan_geometries([g1, g2])
        assert result["room_count"] == 7
        assert len(result["rooms"]) == 7

    def test_confidence_averaged_across_geometries(self):
        g1 = _geom(confidence=0.8)
        g2 = _geom(confidence=0.6)
        result = _merge_floorplan_geometries([g1, g2])
        assert result["geometry_confidence"] == pytest.approx(0.7, abs=0.001)

    def test_scale_source_picks_most_reliable(self):
        """heuristic + ocr_confirmed should resolve to ocr_confirmed."""
        g1 = _geom(scale="heuristic")
        g2 = _geom(scale="ocr_confirmed")
        result = _merge_floorplan_geometries([g1, g2])
        assert result["scale_source"] == "ocr_confirmed"

    def test_scale_source_ocr_dimensions_beats_detector(self):
        g1 = _geom(scale="detector")
        g2 = _geom(scale="ocr_dimensions")
        result = _merge_floorplan_geometries([g1, g2])
        assert result["scale_source"] == "ocr_dimensions"

    def test_heuristic_flags_ored(self):
        """If any geometry has a flag True, the merged result is True."""
        g1 = _geom(flags={
            "derived_from_area_only": False,
            "assumed_floor_height": True,
            "inferred_internal_walls": False,
            "missing_scale_confirmation": False,
        })
        g2 = _geom(flags={
            "derived_from_area_only": True,
            "assumed_floor_height": True,
            "inferred_internal_walls": False,
            "missing_scale_confirmation": False,
        })
        result = _merge_floorplan_geometries([g1, g2])
        assert result["heuristic_flags"]["derived_from_area_only"] is True
        assert result["heuristic_flags"]["assumed_floor_height"] is True
        assert result["heuristic_flags"]["inferred_internal_walls"] is False

    def test_method_set_to_multi_image_merged(self):
        result = _merge_floorplan_geometries([_geom(), _geom()])
        assert result["method"] == "multi_image_merged"

    def test_source_count_recorded(self):
        result = _merge_floorplan_geometries([_geom(), _geom(), _geom()])
        assert result["source_count"] == 3


import pytest  # noqa: E402 (needed for pytest.approx above)

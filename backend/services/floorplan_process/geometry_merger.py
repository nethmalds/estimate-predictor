"""Floorplan geometry merger - aggregates results from multiple floorplan images."""
from __future__ import annotations

_SCALE_PRIORITY = ["ocr_confirmed", "ocr_dimensions", "detector", "heuristic"]


def merge_floorplan_geometries(geometries: list[dict]) -> dict:
    """Merge geometry dicts from multiple floorplan images into one aggregate.

    Strategy:
    - Numeric totals (area, perimeter, walls, openings, rooms): sum.
    - Geometry confidence: average of individual confidence scores.
    - Scale source: pick the most reliable value per _SCALE_PRIORITY.
    - Heuristic flags: OR - flag is True if any image raised it.
    - Rooms list: concatenated.
    - Method: set to multi_image_merged.
    """
    if not geometries:
        return {}
    if len(geometries) == 1:
        return geometries[0]

    total_area      = sum(g.get("total_floor_area_m2", 0.0) for g in geometries)
    total_perimeter = sum(g.get("perimeter_m", 0.0) for g in geometries)
    total_walls     = sum(g.get("wall_length_m", 0.0) for g in geometries)
    total_openings  = sum(g.get("opening_count", 0) for g in geometries)
    total_rooms     = sum(g.get("room_count", 0) for g in geometries)
    all_rooms       = [r for g in geometries for r in (g.get("rooms") or [])]

    confs    = [float(g.get("geometry_confidence", 0.0)) for g in geometries]
    avg_conf = sum(confs) / len(confs)

    best_scale = min(
        (g.get("scale_source", "heuristic") for g in geometries),
        key=lambda s: _SCALE_PRIORITY.index(s) if s in _SCALE_PRIORITY else 99,
    )

    _FLAG_KEYS = (
        "derived_from_area_only",
        "assumed_floor_height",
        "inferred_internal_walls",
        "missing_scale_confirmation",
    )
    merged_flags: dict[str, bool] = {
        key: any(g.get("heuristic_flags", {}).get(key, False) for g in geometries)
        for key in _FLAG_KEYS
    }

    return {
        "total_floor_area_m2": round(total_area, 2),
        "perimeter_m":         round(total_perimeter, 2),
        "wall_length_m":       round(total_walls, 2),
        "opening_count":       total_openings,
        "room_count":          total_rooms,
        "rooms":               all_rooms,
        "geometry_confidence": round(avg_conf, 4),
        "scale_source":        best_scale,
        "heuristic_flags":     merged_flags,
        "method":              "multi_image_merged",
        "source_count":        len(geometries),
        "inferred_area_flag":  any(g.get("inferred_area_flag", False) for g in geometries),
    }

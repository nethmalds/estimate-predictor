"""Deprecated compatibility stub — logic has moved to services.floorplan_process.confidence_scorer."""
from __future__ import annotations

from services.floorplan_process.confidence_scorer import compute_geometry_confidence  # noqa: F401 (re-export)

__all__ = ["compute_geometry_confidence"]

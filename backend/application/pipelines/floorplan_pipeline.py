"""Deprecated compatibility shim — use services.floorplan_process.service.run_pipeline instead."""
from __future__ import annotations

from services.floorplan_process.service import run_pipeline


def execute_floorplan_pipeline(image_path: str) -> dict:
    """Deprecated: delegates to services.floorplan_process.service.run_pipeline."""
    return run_pipeline(image_path)

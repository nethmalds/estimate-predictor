"""Floorplan service — communication facade.

This is the single public surface that external callers use.
It only communicates with other processes and delegates inward to the
internal floorplan modules.  No business logic lives here.
"""
from __future__ import annotations

from services.floorplan_process.orchestrator import run_floorplan_pipeline
from services.floorplan_process.confidence_scorer import compute_geometry_confidence
from services.floorplan_process.geometry_merger import merge_floorplan_geometries


def run_pipeline(image_path: str) -> dict:
    """Public entrypoint for the floorplan processing pipeline.

    Accepts both a local file path and an http(s) URL.

    Returns
    -------
    dict
        Enriched geometry dict including geometry_confidence, scale_source,
        heuristic_flags, and all other fields.
    """
    return run_floorplan_pipeline(image_path)

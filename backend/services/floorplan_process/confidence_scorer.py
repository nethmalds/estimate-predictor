"""Floorplan geometry confidence scoring.

Implements the weighted confidence formula:

    c_g = clamp(β1·c_ocr + β2·c_det + β3·c_scale + β4·c_coverage − β5·p_heuristic, 0, 1)

Coefficients are initial values; calibrate once test data is available.
"""
from __future__ import annotations

# ---------------------------------------------------------------------------
# Coefficients (β values)
# ---------------------------------------------------------------------------
_BETA_OCR    = 0.30   # weight for OCR dimension presence
_BETA_DET    = 0.25   # weight for YOLO detector confidence
_BETA_SCALE  = 0.20   # weight for scale-source quality
_BETA_COV    = 0.15   # weight for room-area coverage
_BETA_HEUR   = 0.10   # heuristic-penalty coefficient

# Scale-source quality scores
_SCALE_SOURCE_SCORE: dict[str, float] = {
    "ocr_confirmed":  1.00,   # area from rooms AND OCR dimensions cross-check
    "ocr_dimensions": 0.80,   # area inferred from OCR dimension tokens
    "detector":       0.60,   # area from YOLO room bounding boxes only
    "area_inferred":  0.40,   # area inferred from partial CV signals
    "heuristic":      0.20,   # pure heuristic fallback
}


def compute_geometry_confidence(
    ocr_confidence: float,
    detector_confidence: float,
    scale_source: str,
    coverage_confidence: float,
    heuristic_flags: dict[str, bool] | None = None,
) -> float:
    """Return a 0–1 geometry confidence score.

    Parameters
    ----------
    ocr_confidence:
        1.0 when OCR dimension tokens were found, 0.0 otherwise.
    detector_confidence:
        Average YOLO detection confidence across all boxes (0–1).
    scale_source:
        How scale was established:
        ``"ocr_confirmed"`` | ``"ocr_dimensions"`` | ``"detector"`` |
        ``"area_inferred"`` | ``"heuristic"``.
    coverage_confidence:
        Fraction of building floor area covered by detected rooms, clamped
        to [0, 1].  Use ``min(room_count / 5.0, 1.0)`` as a proxy.
    heuristic_flags:
        Boolean flags indicating which geometry values were heuristically
        derived.  Each ``True`` flag contributes to the heuristic penalty.
    """
    flags = heuristic_flags or {}

    # Heuristic penalty proportion
    heuristic_count = sum(1 for v in flags.values() if v)
    total_flags = max(len(flags), 1)
    p_heuristic = heuristic_count / total_flags

    scale_conf = _SCALE_SOURCE_SCORE.get(scale_source, 0.20)

    raw = (
        _BETA_OCR   * float(ocr_confidence)
        + _BETA_DET   * float(detector_confidence)
        + _BETA_SCALE * scale_conf
        + _BETA_COV   * float(coverage_confidence)
        - _BETA_HEUR  * p_heuristic
    )
    return round(min(max(raw, 0.0), 1.0), 4)

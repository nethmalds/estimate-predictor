"""Confidence scoring and candidate fusion for the quantity take-off engine.

Each BOQ item may have multiple quantity candidates, one per source:

  candidate_type    source label              description
  ─────────────────────────────────────────────────────────────────
  geometry          "geometry"                Direct CV measurement
  rule_based        "rule_based"              Geometry-derived formula
  parametric        "parametric"              Parameter-driven (no floorplan)
  ml_item_level     "quantity_predictor"      Per-item ML model
  ml_global         "quantity_predictor"      Global ML model (lower weight)

Candidate schema (Phase 3)
---------------------------
Each entry in ``quantity_candidates`` has:
  candidate_type, quantity, unit, confidence, assumptions, method,
  diagnostics, requires_review, source_payload.

Geometry confidence score (Phase 6)
-------------------------------------
Derived from ``geometry_confidence`` field in the floorplan output when
available; falls back to the legacy three-signal formula:

  geo_conf = 0.40 × yolo_avg_conf
           + 0.30 × (1.0 if OCR dimensions were found else 0.0)
           + 0.30 × min(room_count / 5, 1.0)

Candidate confidence weights
-----------------------------
  "geometry"                        → w = max(geo_conf, 0.25)
  "rule_based"                      → w = max(geo_conf × 0.90, 0.20)
  "parametric"                      → w = 0.60
  "quantity_predictor" (item-level) → w = f_m × s_m  (s_m=1.0)
  "quantity_predictor" (global)     → w = f_m × s_m  (s_m=0.75)

Reconciliation — Phase 10
--------------------------
Continuous units (m, m², m³, Kg …):
  q_final = Σ(w_i × q_i) / Σ(w_i)

Discrete units (Nr, Item, Pair, Set …):
  i* = argmax(w_i),  q_final = ceil(q_{i*})

Disagreement score — Phase 11
-------------------------------
  δ = (max(q_i) − min(q_i)) / max(q̄, 1)
"""
from __future__ import annotations

import math

from core.logging.logger import get_logger

logger = get_logger(__name__)

# Discrete units — use winner-takes-all reconciliation, not weighted mean
_DISCRETE_UNITS: frozenset[str] = frozenset({
    "nr", "nr.", "no", "no.", "item", "pair", "set", "each", "lot",
})

# Maximum possible weight for a single candidate (geometry, geo_conf=1.0)
_MAX_SINGLE_WEIGHT = 1.0


def _is_discrete(unit: str | None) -> bool:
    return (unit or "").strip().lower() in _DISCRETE_UNITS


def score_geometry_confidence(geometry: dict) -> float:
    """Return a 0–1 confidence score reflecting how reliable the extracted geometry is.

    Prefers the ``geometry_confidence`` field produced by the Phase 6 orchestrator.
    Falls back to the legacy three-signal formula for backward compatibility.
    """
    if not geometry:
        return 0.0

    # Phase 6 field takes priority
    gc = geometry.get("geometry_confidence")
    if gc is not None:
        return round(float(gc), 4)

    # Legacy fallback
    yolo_conf: float = float(geometry.get("_yolo_avg_conf") or 0.0)
    ocr_dims: list = geometry.get("dimensions_raw") or []
    ocr_score = 1.0 if ocr_dims else 0.0
    room_count: int = int(geometry.get("room_count") or 0)
    room_score = min(room_count / 5.0, 1.0)

    geo_conf = 0.40 * yolo_conf + 0.30 * ocr_score + 0.30 * room_score
    return round(min(max(geo_conf, 0.0), 1.0), 4)


def candidate_weight(
    source: str,
    geo_conf: float,
    *,
    is_item_level: bool = False,
    feature_completeness: float = 1.0,
) -> float:
    """Return the confidence weight for a single quantity candidate.

    Parameters
    ----------
    source:
        One of ``"geometry"``, ``"rule_based"``, ``"parametric"``, or
        ``"quantity_predictor"``.
    geo_conf:
        Geometry confidence score (0–1).
    is_item_level:
        ``True`` when the ML model used a per-item model.
    feature_completeness:
        ML feature completeness score f_m (0–1).  Only used for ML sources.
    """
    if source == "geometry":
        return max(geo_conf, 0.25)
    if source == "rule_based":
        return round(max(geo_conf * 0.90, 0.20), 4)
    if source == "parametric":
        return 0.60
    if source == "quantity_predictor":
        scope_factor = 1.0 if is_item_level else 0.75
        return round(feature_completeness * scope_factor, 4)
    return 0.30  # unknown source


def _build_candidate_meta(
    qty: float,
    source: str,
    weight: float,
    is_item_level: bool,
    unit: str | None = None,
    feature_completeness: float | None = None,
    unknown_features: list[str] | None = None,
    assumptions: list[str] | None = None,
    allocation_mode: str = "direct",
) -> dict:
    """Build a Phase 3 candidate metadata entry."""
    if source == "geometry":
        candidate_type = "geometry"
    elif source == "rule_based":
        candidate_type = "rule_based"
    elif source == "parametric":
        candidate_type = "parametric"
    elif source == "quantity_predictor" and is_item_level:
        candidate_type = "ml_item_level"
    else:
        candidate_type = "ml_global"

    requires_review = (
        candidate_type == "ml_global"
        or (feature_completeness is not None and feature_completeness < 0.50)
        or allocation_mode == "global_allocation"
    )

    diagnostics: dict = {
        "weight": round(weight, 4),
        "is_item_level": is_item_level,
    }
    if feature_completeness is not None:
        diagnostics["feature_completeness"] = feature_completeness
    if unknown_features:
        diagnostics["unknown_features"] = unknown_features

    return {
        "candidate_type":  candidate_type,
        "quantity":        qty,
        "unit":            unit or "",
        "confidence":      round(weight, 4),
        "assumptions":     assumptions or [],
        "method":          source,
        "diagnostics":     diagnostics,
        "requires_review": requires_review,
        "source_payload":  {
            "source": source,
            "allocation_mode": allocation_mode,
        },
    }


def fuse_candidates(
    candidates: list[tuple[float, str, bool]],
    geo_conf: float,
    unit: str | None = None,
    ml_diagnostics: dict | None = None,
) -> tuple[float, float, str, list[dict]]:
    """Fuse multiple quantity candidates into a single reconciled estimate.

    Supports Phase 10 unit-aware reconciliation and Phase 11 disagreement scoring.

    Parameters
    ----------
    candidates:
        List of ``(quantity, source, is_item_level)`` tuples.  Non-positive
        quantities are excluded from fusion.
    geo_conf:
        Geometry confidence score for this floorplan (0–1).
    unit:
        BOQ item unit string (e.g. "Nr", "m²").  Used for discrete detection.
    ml_diagnostics:
        Optional dict from ``predict_quantity`` to pull feature_completeness,
        unknown_feature_names, and allocation_mode.

    Returns
    -------
    (fused_quantity, confidence_score, dominant_source, candidates_metadata)
    """
    ml_diag = ml_diagnostics or {}
    fc = float(ml_diag.get("feature_completeness", 1.0))
    unk = ml_diag.get("unknown_feature_names", [])
    alloc_mode = ml_diag.get("allocation_mode", "direct")

    # Filter out zero/negative quantities
    valid = [(q, src, il) for q, src, il in candidates if q > 0]

    if not valid:
        if candidates:
            _, src, il = candidates[0]
            meta = [_build_candidate_meta(0.0, src, 0.0, il, unit)]
            return 0.0, 0.0, src, meta
        return 0.0, 0.0, "unknown", []

    weights: list[float] = []
    meta: list[dict] = []
    for qty, src, il in valid:
        feat_c = fc if src == "quantity_predictor" else 1.0
        unk_f = unk if src == "quantity_predictor" else []
        amode = alloc_mode if src == "quantity_predictor" else "direct"
        w = candidate_weight(src, geo_conf, is_item_level=il, feature_completeness=feat_c)
        weights.append(w)
        meta.append(_build_candidate_meta(qty, src, w, il, unit, feat_c, unk_f,
                                          allocation_mode=amode))

    total_w = sum(weights)
    discrete = _is_discrete(unit)

    # ── Phase 10: Unit-aware reconciliation ──────────────────────────────────
    if discrete:
        # Winner-takes-all: highest-weight candidate, then ceil
        # Tie-break order: geometry > parametric > ml_item_level > ml_global
        _TIE_ORDER = {"geometry": 0, "rule_based": 1, "parametric": 2,
                      "ml_item_level": 3, "ml_global": 4}

        def _priority(idx: int) -> tuple:
            return (-weights[idx], _TIE_ORDER.get(meta[idx]["candidate_type"], 99))

        winner_idx = min(range(len(valid)), key=_priority)
        winner_qty = valid[winner_idx][0]
        fused = float(math.ceil(winner_qty))
        dominant_source = valid[winner_idx][1]
        # Mark the winning candidate
        meta[winner_idx]["diagnostics"]["discrete_winner"] = True
        meta[winner_idx]["diagnostics"]["discrete_rounding_applied"] = (
            fused != winner_qty
        )
        conf = round(weights[winner_idx] / _MAX_SINGLE_WEIGHT, 4)
    else:
        # Continuous units: weighted mean
        if total_w <= 0:
            fused = sum(c[0] for c in valid) / len(valid)
            fused = round(max(fused, 0.0), 2)
            conf = 0.0
        else:
            fused = sum(w * c[0] for w, c in zip(weights, valid)) / total_w
            fused = round(max(fused, 0.0), 2)
            max_possible_w = len(valid) * _MAX_SINGLE_WEIGHT
            conf = round(min(total_w / max(max_possible_w, 1e-9), 1.0), 4)

        dominant_idx = max(range(len(weights)), key=lambda i: weights[i])
        dominant_source = valid[dominant_idx][1]

    # ── Phase 11: Disagreement score ─────────────────────────────────────────
    if len(valid) > 1:
        qs = [c[0] for c in valid]
        q_bar = sum(qs) / len(qs)
        delta = (max(qs) - min(qs)) / max(q_bar, 1.0)
        for m in meta:
            m["diagnostics"]["disagreement_score"] = round(delta, 4)
    else:
        delta = 0.0

    logger.debug(
        "confidence_scoring fused=%.3f conf=%.4f dominant=%s candidates=%d "
        "discrete=%s delta=%.4f",
        fused, conf, dominant_source, len(valid), discrete, delta,
    )

    return round(max(fused, 0.0), 2), conf, dominant_source, meta

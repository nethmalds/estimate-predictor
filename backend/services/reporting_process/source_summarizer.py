"""Source attribution summarizer - counts BOQ items by their quantity source type."""
from __future__ import annotations

_DISCRETE_UNITS = frozenset({"nr", "nr.", "no", "no.", "item", "pair", "set", "each", "lot"})


def build_source_summary(items: list[dict]) -> dict:
    """Count items by source type for transparency reporting.

    Categorises each item into one of these buckets:
    - geometry_only       : single geometry/rule candidate, no ML fusion
    - parametric_only     : single parametric candidate, no ML fusion
    - ml_only             : single ML candidate (item-level)
    - fused               : 2+ candidates were weighted-fused
    - globally_allocated  : quantity derived from category-level ML global model
    - low_confidence      : quantity_confidence < 0.50
    - discretely_rounded  : discrete unit item (whole-number check applied)
    - unknown             : no other category matched
    """
    summary: dict[str, int] = {
        "geometry_only":      0,
        "parametric_only":    0,
        "ml_only":            0,
        "fused":              0,
        "globally_allocated": 0,
        "low_confidence":     0,
        "discretely_rounded": 0,
        "unknown":            0,
    }

    for item in items:
        candidates      = item.get("quantity_candidates") or []
        recon           = item.get("reconciliation_summary") or {}
        review_flags    = recon.get("review_flags") or []
        candidate_count = recon.get("candidate_count") or len(candidates)
        source          = item.get("quantity_source") or "unknown"
        unit            = str(item.get("unit") or item.get("preferred_unit") or "").lower().strip()
        conf            = float(item.get("quantity_confidence") or item.get("quantity_confidence_score") or 0.0)

        if unit in _DISCRETE_UNITS:
            summary["discretely_rounded"] += 1

        if conf < 0.50:
            summary["low_confidence"] += 1

        if "global_allocation_only" in review_flags or "global_allocation_used" in review_flags:
            summary["globally_allocated"] += 1
            continue

        if candidate_count >= 2:
            summary["fused"] += 1
            continue

        cand_types = [c.get("candidate_type", "") for c in candidates] if candidates else [source]
        if any(t in ("geometry", "rule_based") for t in cand_types):
            summary["geometry_only"] += 1
        elif any(t == "parametric" for t in cand_types):
            summary["parametric_only"] += 1
        elif any(t in ("ml_item_level", "quantity_predictor") for t in cand_types):
            summary["ml_only"] += 1
        else:
            summary["unknown"] += 1

    return summary

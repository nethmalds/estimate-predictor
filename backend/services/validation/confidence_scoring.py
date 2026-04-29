from core.logging.logger import get_logger

logger = get_logger(__name__)


def score_confidence(
    project_info: dict,
    floorplan_summary: dict | None = None,
    warnings: list[str] | None = None,
    boq_items: list[dict] | None = None,
) -> dict:
    """Calculate a confidence score for the estimate.

    Scoring breakdown (C15 fix):
    - Base: 0.50 (lowered from 0.70 so unmatched items have real impact)
    - Floorplan data present: +0.10
    - All MVED parameters collected (no defaults used): +0.10
    - Defaults applied penalty: -0.04 per default field used (max -0.20)
    - Validation warnings: -0.05 per warning (max -0.20)
    - Unmatched / zero-rate items: -0.30 * unmatched_fraction
    - needs_rate_review items: -0.05 per item (max -0.15)
    """
    score = 0.50
    reasons: list[str] = []

    # Floorplan bonus
    if floorplan_summary and floorplan_summary.get("total_floor_area_m2"):
        score += 0.10
        reasons.append("floorplan_data")

    # Parameter completeness bonus (no defaults applied)
    applied_defaults: list[str] = project_info.get("applied_defaults") or []
    if project_info.get("parameters") and not applied_defaults:
        score += 0.10
        reasons.append("full_mved_collected")
    elif applied_defaults:
        penalty = min(0.04 * len(applied_defaults), 0.20)
        score -= penalty
        reasons.append(f"defaults_applied:{','.join(applied_defaults)}")

    # Validation warnings penalty
    if warnings:
        penalty = min(0.05 * len(warnings), 0.20)
        score -= penalty
        reasons.append(f"validation_warnings:{len(warnings)}")

    # BOQ match quality penalty (C15)
    if boq_items:
        total = len(boq_items)
        unmatched = sum(
            1 for it in boq_items
            if it.get("match_type") == "no_match" or (
                not it.get("is_contractual") and float(it.get("rate") or 0) == 0.0
            )
        )
        review_items = sum(1 for it in boq_items if it.get("needs_rate_review"))

        if total > 0 and unmatched > 0:
            unmatched_fraction = unmatched / total
            score -= round(unmatched_fraction * 0.30, 4)
            reasons.append(f"unmatched_items:{unmatched}/{total}")

        if review_items > 0:
            score -= min(0.05 * review_items, 0.15)
            reasons.append(f"rate_review_items:{review_items}")

    score = round(max(0.0, min(score, 1.0)), 4)
    logger.info("confidence_score score=%.3f reasons=%s", score, reasons)
    return {
        "score": score,
        "reasons": reasons,
        "defaults_applied": applied_defaults,
    }

from core.logging.logger import get_logger

logger = get_logger(__name__)


def score_confidence(
    project_info: dict,
    floorplan_summary: dict | None = None,
    warnings: list[str] | None = None,
    boq_items: list[dict] | None = None,
) -> dict:
    """Calculate a confidence score for the estimate.

    Scoring breakdown (Phase 13 update):
    - Base: 0.50
    - Floorplan data present: +0.10
    - All MVED parameters collected (no defaults used): +0.10
    - Defaults applied penalty: -0.04 per default field used (max -0.20)
    - Validation warnings: -0.05 per warning (max -0.20)
    - Unmatched / zero-rate items: -0.30 * unmatched_fraction
    - needs_rate_review items: -0.05 per item (max -0.15)
    - Low geometry_confidence (< 0.50): proportional penalty (max -0.15)
    - Low average feature_completeness (< 0.70): -0.05 per 0.10 below threshold (max -0.15)
    - High unknown_feature_count: -0.02 per item with unknown features (max -0.10)
    - Items with disagreement_score > 0.50: -0.03 per item (max -0.12)
    - Global-allocation-only items: -0.05 per item proportion (max -0.10)
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

    # BOQ match quality + Phase 13 item-level diagnostics
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

        # Phase 13: geometry_confidence penalty
        geo_conf = float((floorplan_summary or {}).get("geometry_confidence") or 1.0)
        if geo_conf < 0.50:
            geo_penalty = min((0.50 - geo_conf) * 0.30, 0.15)
            score -= geo_penalty
            reasons.append(f"low_geometry_confidence:{geo_conf:.2f}")

        # Phase 13: feature_completeness average penalty
        fc_vals = [
            float(it.get("feature_completeness") or 1.0)
            for it in boq_items
            if "feature_completeness" in it
        ]
        if fc_vals:
            avg_fc = sum(fc_vals) / len(fc_vals)
            if avg_fc < 0.70:
                steps_below = (0.70 - avg_fc) / 0.10
                fc_penalty = min(0.05 * steps_below, 0.15)
                score -= fc_penalty
                reasons.append(f"low_feature_completeness:{avg_fc:.2f}")

        # Phase 13: unknown_feature_count penalty
        unknown_count = sum(
            1 for it in boq_items
            if int(it.get("unknown_feature_count") or 0) > 0
        )
        if unknown_count > 0:
            score -= min(0.02 * unknown_count, 0.10)
            reasons.append(f"items_with_unknown_features:{unknown_count}")

        # Phase 13: high disagreement penalty
        high_disagreement_count = sum(
            1 for it in boq_items
            if float((it.get("reconciliation_summary") or {}).get("disagreement_score") or 0.0) > 0.50
        )
        if high_disagreement_count > 0:
            score -= min(0.03 * high_disagreement_count, 0.12)
            reasons.append(f"high_disagreement_items:{high_disagreement_count}")

        # Phase 13: global allocation penalty
        if total > 0:
            global_alloc_count = sum(
                1 for it in boq_items
                if "global_allocation" in ((it.get("reconciliation_summary") or {}).get("review_flags") or [])
                or "global_allocation_only" in ((it.get("reconciliation_summary") or {}).get("review_flags") or [])
                or (it.get("quantity_source") == "quantity_predictor"
                    and not (it.get("reconciliation_summary") or {}).get("candidate_count", 1) > 1)
            )
            if global_alloc_count > 0:
                global_fraction = global_alloc_count / total
                score -= min(global_fraction * 0.10, 0.10)
                reasons.append(f"global_allocation_items:{global_alloc_count}/{total}")

    score = round(max(0.0, min(score, 1.0)), 4)
    logger.info("confidence_score score=%.3f reasons=%s", score, reasons)
    return {
        "score": score,
        "reasons": reasons,
        "defaults_applied": applied_defaults,
    }

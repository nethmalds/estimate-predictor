


def build_report(payload: dict) -> dict:
    project_info = payload.get("project_info") or {}
    parameters = project_info.get("parameters") or {}
    boq_items: list[dict] = payload.get("boq_items") or []
    costs: dict = payload.get("costs") or {}
    total = costs.get("total")
    confidence = payload.get("confidence", {}).get("score")
    defaults_applied: list[str] = project_info.get("applied_defaults") or []

    # C16: collect items that need manual rate review
    rate_review_items = [
        {
            "description": it.get("description"),
            "category": it.get("category"),
            "match_type": it.get("match_type"),
            "bsr_item_no": it.get("bsr_item_no"),
        }
        for it in boq_items
        if it.get("needs_rate_review") or it.get("match_type") == "no_match"
    ]

    return {
        "summary": {
            "total": total,
            "preliminaries": costs.get("preliminaries"),
            "contingencies": costs.get("contingencies"),
            "base_total": costs.get("base_total"),
            "confidence": confidence,
            "defaults_applied": defaults_applied,
            "rate_review_items": rate_review_items,
            "mved": {
                "floors": project_info.get("floors"),
                "bedrooms": parameters.get("bedrooms"),
                "bathrooms": parameters.get("bathrooms"),
                "built_up_area": parameters.get("built_up_area"),
                "finish_level": parameters.get("finish_level"),
                "roof_type": parameters.get("roof_type"),
            },
            "sources": payload.get("sources"),
        },
        "details": payload,
    }

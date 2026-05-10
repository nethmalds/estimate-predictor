


def build_report(payload: dict) -> dict:
    project_info = payload.get("project_info") or {}
    parameters = project_info.get("parameters") or {}
    boq_items: list[dict] = payload.get("boq_items") or []
    costs: dict = payload.get("costs") or {}
    floorplan_meta: dict = payload.get("floorplan") or {}
    total = costs.get("total")
    confidence = payload.get("confidence", {}).get("score")
    defaults_applied: list[str] = project_info.get("applied_defaults") or []
    preprocessing_warnings: list[str] = project_info.get("preprocessing_warnings") or []

    # Items needing manual rate review
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

    # BOQ source provenance breakdown
    source_breakdown: dict[str, int] = {}
    for item in boq_items:
        src = item.get("source") or "unknown"
        source_breakdown[src] = source_breakdown.get(src, 0) + 1

    # Floorplan audit
    floorplan_audit = {
        "uploaded": bool(floorplan_meta.get("available") or floorplan_meta.get("accepted") is not None),
        "accepted": floorplan_meta.get("accepted"),
        "geometry_confidence": floorplan_meta.get("geometry_confidence"),
        "rejection_reason": floorplan_meta.get("rejection_reason"),
        "total_floor_area_m2": floorplan_meta.get("total_floor_area_m2"),
        "room_count": floorplan_meta.get("room_count"),
        "heuristic_flags": floorplan_meta.get("heuristic_flags"),
    }

    return {
        "summary": {
            "total": total,
            "base_total": costs.get("base_total"),
            "external_works_total": costs.get("external_works_total"),
            "preliminaries": costs.get("preliminaries"),
            "preliminaries_rate": costs.get("preliminaries_rate"),
            "contingencies": costs.get("contingencies"),
            "contingencies_rate": costs.get("contingencies_rate"),
            "confidence": confidence,
            "defaults_applied": defaults_applied,
            "preprocessing_warnings": preprocessing_warnings,
            "rate_review_items": rate_review_items,
            "boq_source_breakdown": source_breakdown,
            "floorplan_audit": floorplan_audit,
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

def build_report(payload: dict) -> dict:
    project_info = payload.get("project_info") or {}
    parameters = project_info.get("parameters") or {}
    return {
        "summary": {
            "total": payload.get("costs", {}).get("total"),
            "confidence": payload.get("confidence", {}).get("score"),
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

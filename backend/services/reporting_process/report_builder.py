from core.logging.logger import get_logger

logger = get_logger(__name__)


def build_report(payload: dict) -> dict:
    project_info = payload.get("project_info") or {}
    parameters = project_info.get("parameters") or {}
    total = payload.get("costs", {}).get("total")
    confidence = payload.get("confidence", {}).get("score")
    boq_count = len(payload.get("boq_items") or [])
    logger.info("report_built boq_items=%d total=%.2f confidence=%.3f", boq_count, total or 0.0, confidence or 0.0)
    return {
        "summary": {
            "total": total,
            "confidence": confidence,
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

from core.logging.logger import get_logger

logger = get_logger(__name__)


def validate_quantities(items: list[dict]) -> dict:
    warnings: list[str] = []
    for item in items:
        quantity = float(item.get("quantity") or 0.0)
        if quantity <= 0:
            warnings.append(f"Non-positive quantity for item: {item.get('description')}")
    is_valid = len(warnings) == 0
    logger.info("quantity_validation items=%d warnings=%d is_valid=%s", len(items), len(warnings), is_valid)
    if warnings:
        for w in warnings:
            logger.warning("quantity_warning: %s", w)
    return {"warnings": warnings, "is_valid": is_valid}

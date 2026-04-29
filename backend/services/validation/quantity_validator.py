from core.logging.logger import get_logger

logger = get_logger(__name__)

# Upper-bound sanity limits per category (catches formula bugs producing wild numbers)
# These are intentionally generous — just a circuit-breaker, not an accuracy check.
_CATEGORY_MAX_QUANTITY: dict[str, float] = {
    "concrete_works": 5000.0,        # m³
    "formwork": 30000.0,             # m²
    "reinforcement": 500000.0,       # kg
    "excavation_and_earthwork": 10000.0,  # m³
    "brick_masonry": 20000.0,        # m²
    "plastering_and_rendering": 30000.0,  # m²
    "painting_and_finishes": 30000.0,     # m²
    "flooring_and_tiling": 20000.0,       # m²
    "roofing_and_ceiling": 10000.0,       # m²
    "electrical_and_mechanical": 1000.0,  # Nr
    "sanitary_and_plumbing": 500.0,       # Nr
}


def validate_quantities(items: list[dict]) -> dict:
    """Validate quantities for all BOQ items.

    Checks performed (C12 fix):
    - Non-positive quantity
    - Exceeds category upper-bound sanity limit
    - Rate = 0.0 on a non-contractual item (flags as ``missing_rate``)
    - ``needs_rate_review`` flag (from BSR matching stage)
    """
    warnings: list[str] = []
    missing_rate_items: list[str] = []
    rate_review_items: list[str] = []

    for item in items:
        desc = item.get("description") or "?"
        category = (item.get("category") or "").lower()
        is_contractual = item.get("is_contractual", False)

        # Check 1: non-positive quantity
        try:
            quantity = float(item.get("quantity") or 0.0)
        except (TypeError, ValueError):
            quantity = 0.0

        if quantity <= 0:
            warnings.append(f"Non-positive quantity for item: {desc}")

        # Check 2: unrealistically large quantity
        upper = _CATEGORY_MAX_QUANTITY.get(category)
        if upper and quantity > upper:
            warnings.append(
                f"Suspiciously large quantity {quantity:.1f} for '{desc}' "
                f"(category '{category}', max expected {upper:.0f})"
            )

        # Check 3: zero rate on a non-contractual item
        try:
            rate = float(item.get("rate") or 0.0)
        except (TypeError, ValueError):
            rate = 0.0

        if rate == 0.0 and not is_contractual:
            missing_rate_items.append(desc)
            warnings.append(f"Rate is 0 on non-contractual item: {desc}")

        # Check 4: BSR matching flagged this item for review
        if item.get("needs_rate_review"):
            rate_review_items.append(desc)

    is_valid = len(warnings) == 0
    logger.info(
        "quantity_validation items=%d warnings=%d missing_rate=%d rate_review=%d is_valid=%s",
        len(items),
        len(warnings),
        len(missing_rate_items),
        len(rate_review_items),
        is_valid,
    )
    for w in warnings:
        logger.warning("quantity_warning: %s", w)

    return {
        "warnings": warnings,
        "is_valid": is_valid,
        "missing_rate_items": missing_rate_items,
        "rate_review_items": rate_review_items,
    }

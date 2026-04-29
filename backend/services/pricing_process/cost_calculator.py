from core.logging.logger import get_logger
from core.config.settings import settings

logger = get_logger(__name__)


def calculate_costs(
    items: list[dict],
    preliminaries_rate: float | None = None,
    contingencies_rate: float | None = None,
) -> dict:
    """Calculate construction costs with Sri Lankan BSR standard rates.

    Parameters
    ----------
    items:
        The validated, matched BOQ items with ``rate`` and ``quantity``.
    preliminaries_rate:
        Fraction to add as preliminaries (default from ``settings``).
    contingencies_rate:
        Fraction to add as contingencies (default from ``settings``).

    Returns
    -------
    dict
        Full cost breakdown including subtotals, preliminaries, contingencies,
        and the enriched item list with per-item ``cost`` field.
    """
    if preliminaries_rate is None:
        preliminaries_rate = settings.preliminaries_rate
    if contingencies_rate is None:
        contingencies_rate = settings.contingencies_rate

    subtotals: dict[str, float] = {}
    detailed: list[dict] = []

    for item in items:
        try:
            rate = float(item.get("rate") or 0.0)
            quantity = float(item.get("quantity") or 0.0)
            cost = rate * quantity
        except (TypeError, ValueError) as exc:
            # C14: one bad item must not crash the entire calculation
            logger.warning(
                "cost_item_skip description=%r error=%s",
                item.get("description", "?"),
                exc,
            )
            cost = 0.0

        category = item.get("category") or "uncategorized"
        subtotals[category] = subtotals.get(category, 0.0) + cost
        item_copy = dict(item)
        item_copy["cost"] = round(cost, 2)
        detailed.append(item_copy)

    base_total = sum(subtotals.values())
    preliminaries = base_total * preliminaries_rate
    contingencies = base_total * contingencies_rate
    total = base_total + preliminaries + contingencies

    logger.info(
        "cost_calculation items=%d base_total=%.2f preliminaries=%.2f "
        "contingencies=%.2f total=%.2f",
        len(items),
        base_total,
        preliminaries,
        contingencies,
        total,
    )
    return {
        "subtotals": subtotals,
        "base_total": round(base_total, 2),
        "preliminaries": round(preliminaries, 2),
        "preliminaries_rate": preliminaries_rate,
        "contingencies": round(contingencies, 2),
        "contingencies_rate": contingencies_rate,
        "total": round(total, 2),
        "items": detailed,
    }

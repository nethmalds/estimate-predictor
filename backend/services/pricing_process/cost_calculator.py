from core.config.settings import settings

# Categories that belong to the external works scope — surfaced as an
# explicit subtotal so the client can see their direct pricing impact.
_EXTERNAL_WORKS_CATEGORIES: frozenset[str] = frozenset({
    "external_and_civil_works",
    "external",
})


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
        Full cost breakdown including category subtotals, explicit external
        works subtotal, preliminaries, contingencies, and the enriched item
        list with per-item ``cost`` field.
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
        except (TypeError, ValueError):
            # One bad item must not crash the entire calculation
            cost = 0.0

        category = item.get("category") or "uncategorized"
        subtotals[category] = subtotals.get(category, 0.0) + cost
        item_copy = dict(item)
        item_copy["cost"] = round(cost, 2)
        detailed.append(item_copy)

    base_total = sum(subtotals.values())

    # Explicit external works subtotal — sum of all external-scope categories
    external_works_total = sum(
        v for k, v in subtotals.items()
        if k.lower() in _EXTERNAL_WORKS_CATEGORIES
    )

    preliminaries = base_total * preliminaries_rate
    contingencies = base_total * contingencies_rate
    total = base_total + preliminaries + contingencies

    # Cost consistency validation
    consistency_warnings: list[str] = []

    # 1. Line-item cost cross-check: sum of item costs must equal sum of subtotals
    item_cost_sum = sum(float(it.get("cost") or 0.0) for it in detailed)
    subtotal_sum = sum(subtotals.values())
    if abs(item_cost_sum - subtotal_sum) > 0.05:
        consistency_warnings.append(
            f"Line-item cost sum ({item_cost_sum:.2f}) differs from category "
            f"subtotal sum ({subtotal_sum:.2f}) — rounding drift detected."
        )

    # 2. External works subtotal consistency: must not exceed base total
    if external_works_total > base_total and base_total > 0:
        consistency_warnings.append(
            f"External works total ({external_works_total:.2f}) exceeds base total "
            f"({base_total:.2f}) — category assignment may be incorrect."
        )

    # 3. Grand total consistency: base + prelim + contingencies must equal total
    expected_total = round(base_total + preliminaries + contingencies, 2)
    if abs(expected_total - round(total, 2)) > 0.05:
        consistency_warnings.append(
            f"Grand total ({total:.2f}) does not match "
            f"base + preliminaries + contingencies ({expected_total:.2f})."
        )

    return {
        "subtotals": subtotals,
        "base_total": round(base_total, 2),
        "external_works_total": round(external_works_total, 2),
        "preliminaries": round(preliminaries, 2),
        "preliminaries_rate": preliminaries_rate,
        "contingencies": round(contingencies, 2),
        "contingencies_rate": contingencies_rate,
        "total": round(total, 2),
        "consistency_warnings": consistency_warnings,
        "items": detailed,
    }

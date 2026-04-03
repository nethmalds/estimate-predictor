def calculate_costs(items: list[dict], contingencies_rate: float = 0.05) -> dict:
	subtotals: dict[str, float] = {}
	detailed: list[dict] = []

	for item in items:
		rate = float(item.get("rate") or 0.0)
		quantity = float(item.get("quantity") or 0.0)
		cost = rate * quantity
		category = item.get("category") or "uncategorized"
		subtotals[category] = subtotals.get(category, 0.0) + cost
		item_copy = dict(item)
		item_copy["cost"] = cost
		detailed.append(item_copy)

	base_total = sum(subtotals.values())
	contingencies = base_total * contingencies_rate
	total = base_total + contingencies

	return {
		"subtotals": subtotals,
		"base_total": base_total,
		"contingencies": contingencies,
		"contingencies_rate": contingencies_rate,
		"total": total,
		"items": detailed,
	}

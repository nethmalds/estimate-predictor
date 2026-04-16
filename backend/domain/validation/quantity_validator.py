def validate_quantities(items: list[dict]) -> dict:
	warnings: list[str] = []
	for item in items:
		quantity = float(item.get("quantity") or 0.0)
		if quantity <= 0:
			warnings.append(f"Non-positive quantity for item: {item.get('description')}")
	return {"warnings": warnings, "is_valid": len(warnings) == 0}

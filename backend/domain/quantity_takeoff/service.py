from domain.quantity_takeoff.quantity_calculator import estimate_quantity, parse_area


def compute_quantities(boq_items: list[dict], project_info: dict, floorplan_summary: dict | None = None) -> list[dict]:
	parameters = project_info.get("parameters") or {}
	built_up_area = parse_area(parameters.get("built_up_area"))
	floors = project_info.get("floors") or 1

	computed: list[dict] = []
	for item in boq_items:
		quantity, method = estimate_quantity(item.get("category", ""), built_up_area, floors)
		item_copy = dict(item)
		item_copy["quantity"] = quantity
		item_copy["quantity_method"] = method
		if floorplan_summary:
			item_copy["floorplan"] = floorplan_summary.get("summary")
		computed.append(item_copy)

	return computed

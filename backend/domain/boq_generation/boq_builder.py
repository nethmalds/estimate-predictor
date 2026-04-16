from typing import Any


def build_boq_items(project_info: dict, floorplan_summary: dict | None = None) -> list[dict[str, Any]]:
	building_type = (project_info.get("building_type") or "").lower()
	floors = project_info.get("floors") or 1
	scope = _normalize_scope(project_info)

	items: list[dict[str, Any]] = []
	items.append(_make_item("Site preparation and setting out", "preliminaries"))
	items.append(_make_item("Foundation excavation and PCC", "foundation"))
	items.append(_make_item("RCC structural frame", "structure"))
	items.append(_make_item("Masonry and block work", "masonry"))
	items.append(_make_item("Plastering and surface finishing", "finishes"))
	items.append(_make_item("Flooring and skirting", "finishes"))
	items.append(_make_item("Roofing and waterproofing", "roof"))

	if "residential" in building_type:
		items.append(_make_item("Internal doors and windows", "openings"))
	if scope == "extensive":
		items.append(_make_item("External works and drainage", "external"))

	for item in items:
		item["floors"] = floors
		item["source"] = "rule_based"

	if floorplan_summary:
		items.append(_make_item("Floor plan derived quantities", "floorplan"))

	return items


def _normalize_scope(project_info: dict) -> str:
	parameters = project_info.get("parameters") or {}
	scope = parameters.get("external_works_scope")
	if not scope:
		return "basic"
	return str(scope).strip().lower()


def _make_item(description: str, category: str) -> dict[str, Any]:
	return {"description": description, "category": category}

import re


def parse_area(value: str | None) -> float | None:
	if not value:
		return None
	match = re.search(r"([\d.]+)", str(value))
	if not match:
		return None
	try:
		return float(match.group(1))
	except ValueError:
		return None


def estimate_quantity(category: str, built_up_area: float | None, floors: int) -> tuple[float, str]:
	if not built_up_area:
		return 1.0, "default"

	if category in {"foundation", "structure", "masonry"}:
		return built_up_area * max(floors, 1) * 0.8, "area_scaled"
	if category == "finishes":
		return built_up_area * max(floors, 1), "area_direct"
	if category == "roof":
		return built_up_area, "area_direct"
	if category == "openings":
		return max(built_up_area / 10.0, 1.0), "area_ratio"
	if category == "external":
		return built_up_area * 0.3, "area_ratio"
	return 1.0, "default"

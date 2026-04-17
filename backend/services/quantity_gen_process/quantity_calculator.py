import re
from typing import Any


_DEFAULT_BUILT_UP_AREA = 1800.0


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


def estimate_quantity(
    category: str,
    built_up_area: float | None,
    floors: int,
    parameters: dict[str, Any] | None = None,
) -> tuple[float, str]:
    return _estimate_with_model_b_stub(category, built_up_area, floors, parameters or {})


def _estimate_with_model_b_stub(
    category: str,
    built_up_area: float | None,
    floors: int,
    parameters: dict[str, Any],
) -> tuple[float, str]:
    base_area = built_up_area or _DEFAULT_BUILT_UP_AREA
    floor_count = max(int(floors or 1), 1)
    bedrooms = _coerce_int(parameters.get("bedrooms")) or 2
    bathrooms = _coerce_int(parameters.get("bathrooms")) or 1

    if category == "preliminaries":
        return 1.0, "model_b_stub"
    if category == "site":
        return base_area * 0.08, "model_b_stub"
    if category == "foundation":
        return base_area * floor_count * 0.6, "model_b_stub"
    if category == "structure":
        return base_area * floor_count * 0.75, "model_b_stub"
    if category == "masonry":
        return base_area * floor_count * 0.65, "model_b_stub"
    if category == "finishes":
        return base_area * floor_count * 1.1, "model_b_stub"
    if category == "roof":
        return base_area * 1.05, "model_b_stub"
    if category == "openings":
        return max((bedrooms * 2.0) + (bathrooms * 1.5) + 2.0, 4.0), "model_b_stub"
    if category == "electrical":
        return max((base_area / 150.0) * floor_count, 6.0), "model_b_stub"
    if category == "plumbing":
        return max((bathrooms * 4.0) + (bedrooms * 1.5), 4.0), "model_b_stub"
    if category == "external":
        return base_area * 0.25, "model_b_stub"
    return 1.0, "model_b_stub"


def _coerce_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None

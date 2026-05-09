"""Rate resolver — applies location and soil condition adjusters to BSR base rates (Q3 fix)."""


# Location-based cost adjustment factors relative to Colombo baseline.
# Source: BSR 2025 regional cost indices.
_LOCATION_FACTORS: dict[str, float] = {
    "colombo": 1.00,
    "gampaha": 0.97,
    "kalutara": 0.95,
    "kandy": 0.93,
    "galle": 0.94,
    "matara": 0.92,
    "jaffna": 0.95,
    "batticaloa": 0.90,
    "anuradhapura": 0.91,
    "polonnaruwa": 0.90,
    "badulla": 0.88,
    "ratnapura": 0.89,
    "kurunegala": 0.93,
    "puttalam": 0.91,
    "nuwara eliya": 0.87,
    "matale": 0.91,
    "kegalle": 0.92,
    "monaragala": 0.88,
    "hambantota": 0.91,
    "ampara": 0.89,
    "trincomalee": 0.90,
    "kilinochchi": 0.90,
    "mullaitivu": 0.88,
    "vavuniya": 0.90,
    "mannar": 0.89,
}

# Soil condition adjustment factors applied to earthwork and foundation categories.
_SOIL_FACTORS: dict[str, dict[str, float]] = {
    "ordinary soil": {
        "excavation_and_earthwork": 1.00,
        "piling_and_substructure": 1.00,
    },
    "medium soil": {
        "excavation_and_earthwork": 1.20,
        "piling_and_substructure": 1.10,
    },
    "hard soil": {
        "excavation_and_earthwork": 1.50,
        "piling_and_substructure": 1.25,
    },
    "rock": {
        "excavation_and_earthwork": 2.20,
        "piling_and_substructure": 1.80,
    },
}


def resolve_rate(item: dict, project_info: dict) -> float:
    """Apply location and soil condition adjusters to the BSR base rate.

    Parameters
    ----------
    item:
        A matched BOQ item with a ``rate`` field.
    project_info:
        The full project info dict (must include ``parameters``).

    Returns
    -------
    float
        The adjusted rate.
    """
    base_rate = float(item.get("rate") or 0.0)
    if base_rate == 0.0:
        return 0.0

    parameters = project_info.get("parameters") or {}
    location = (parameters.get("location") or "colombo").strip().lower()
    soil_condition = (parameters.get("soil_condition") or "ordinary soil").strip().lower()
    category = (item.get("category") or "").strip().lower()

    # Location factor
    location_factor = _LOCATION_FACTORS.get(location, 1.00)

    # Soil factor (only for affected categories)
    soil_factor = 1.00
    soil_adjustments = _SOIL_FACTORS.get(soil_condition, {})
    if category in soil_adjustments:
        soil_factor = soil_adjustments[category]

    adjusted_rate = round(base_rate * location_factor * soil_factor, 2)

    if location_factor != 1.00 or soil_factor != 1.00:
        item["rate_adjustment"] = {
            "location_factor": location_factor,
            "soil_factor": soil_factor,
        }

    return adjusted_rate

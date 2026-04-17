from typing import Any


_REQUIRED_ROOT_FIELDS = [
    "floors",
]

_REQUIRED_PARAMETER_FIELDS = [
    "bedrooms",
    "bathrooms",
    "built_up_area",
    "finish_level",
    "roof_type",
]


_QUESTIONS = {
    "floors": "How many floors (storeys) will the building have?",
    "bedrooms": "How many bedrooms are required?",
    "bathrooms": "How many bathrooms are required?",
    "built_up_area": "What is the total built-up area you have in mind (in square feet or square meters)? If you are unsure, we can start with a baseline (e.g., 1,800 sq. ft.) and adjust later.",
    "finish_level": "Could you tell me about the level of finishes you're looking for? (Options: 1. Standard / Budget, 2. Semi-Luxury, 3. Full Luxury)",
    "roof_type": "What type of roof will you use? (Options: Flat concrete slab, Clay tile roof, Asbestos sheet roof)",
}


def find_missing_fields(project_info: dict) -> list[str]:
    parameters: dict[str, Any] = project_info.get("parameters") or {}
    missing: list[str] = []
    for field in _REQUIRED_ROOT_FIELDS:
        if not project_info.get(field):
            missing.append(field)
    for field in _REQUIRED_PARAMETER_FIELDS:
        if not parameters.get(field):
            missing.append(field)
    return missing


def build_clarification_questions(missing_fields: list[str]) -> list[str]:
    return [_QUESTIONS.get(field, f"Please provide {field}.") for field in missing_fields]


def merge_parameters(project_info: dict, overrides: dict | None) -> dict:
    if not overrides:
        return project_info
    parameters = project_info.get("parameters") or {}
    for key, value in overrides.items():
        if value is None:
            continue
        parameters[key] = value
    project_info["parameters"] = parameters
    return project_info

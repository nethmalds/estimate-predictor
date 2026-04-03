from typing import Any


_REQUIRED_FIELDS = [
    "built_up_area",
    "finish_level",
    "structural_system",
    "roof_type",
    "location",
    "soil_condition",
    "drainage_type",
    "external_works_scope",
]


_QUESTIONS = {
    "built_up_area": "What is the built-up area (in square meters)?",
    "finish_level": "What finish level should be used (basic, standard, premium)?",
    "structural_system": "What structural system is planned (e.g., RCC frame, load-bearing)?",
    "roof_type": "What roof type should be used (flat slab, pitched, terrace)?",
    "location": "Where is the project located (city/region)?",
    "soil_condition": "What is the soil condition (ordinary, hard, rock)?",
    "drainage_type": "What drainage type is expected (surface, underground, mixed)?",
    "external_works_scope": "What is the scope of external works (none, basic, extensive)?",
}


def find_missing_fields(project_info: dict) -> list[str]:
    parameters: dict[str, Any] = project_info.get("parameters") or {}
    missing = [field for field in _REQUIRED_FIELDS if not parameters.get(field)]
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

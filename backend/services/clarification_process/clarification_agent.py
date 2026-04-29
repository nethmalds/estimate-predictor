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
    "ceiling_type",
]

# Sri Lankan construction defaults — applied silently for non-MVED fields.
# These are never shown to the user as questions; they are logged at WARNING
# level in the transparency layer whenever they are actually used.
_PARAMETER_DEFAULTS: dict[str, str] = {
    "location": "Colombo",
    "soil_condition": "Ordinary Soil",
    "structural_system": "RC Frame",
    "drainage": "Gravity",
    "external_works": "Standard",
}

# Fields whose questions must be answered via a dropdown widget in the frontend.
# Each entry maps the field name to its list of {value, label} options.
_DROPDOWN_FIELDS: dict[str, list[dict[str, str]]] = {
    "finish_level": [
        {"value": "standard", "label": "Standard / Budget"},
        {"value": "semi-luxury", "label": "Semi-Luxury"},
        {"value": "full luxury", "label": "Full Luxury"},
    ],
    "roof_type": [
        {"value": "rc flat slab", "label": "Flat Concrete Slab"},
        {"value": "clay tile", "label": "Clay Tile Roof"},
        {"value": "asbestos sheet", "label": "Asbestos Sheet Roof"},
    ],
    "ceiling_type": [
        {"value": "gypsum", "label": "Gypsum Board"},
        {"value": "concrete", "label": "Concrete (No False Ceiling)"},
        {"value": "timber", "label": "Timber"},
        {"value": "pvc", "label": "PVC"},
    ],
}

_QUESTIONS = {
    "floors": "How many floors (storeys) will the building have?",
    "bedrooms": "How many bedrooms are required?",
    "bathrooms": "How many bathrooms are required?",
    "built_up_area": "What is the total built-up area? Select a range or enter a custom size.",
    "finish_level": "What level of finishes are you looking for?",
    "roof_type": "What type of roof will you use?",
    "ceiling_type": "What type of ceiling finish will be used?",
}

_CEILING_TYPE_MAP: dict[str, str] = {
    "gypsum": "gypsum",
    "gypsum board": "gypsum",
    "1": "gypsum",
    "concrete": "concrete",
    "no false ceiling": "concrete",
    "2": "concrete",
    "timber": "timber",
    "wood": "timber",
    "3": "timber",
    "pvc": "pvc",
    "4": "pvc",
}

# Validation rules for integer fields: (min_inclusive, max_inclusive, error_message)
_INT_FIELD_RULES: dict[str, tuple[int, int, str]] = {
    "floors": (1, 100, "Number of floors must be at least 1. Please enter a valid positive number (e.g. 1, 2, 3)."),
    "bedrooms": (1, 50, "Number of bedrooms must be at least 1. Please enter a valid positive number."),
    "bathrooms": (1, 50, "Number of bathrooms must be at least 1. Please enter a valid positive number."),
}


def normalize_ceiling_type(value: str) -> str | None:
    """Map a raw user answer to a canonical ceiling type string."""
    cleaned = value.strip().lower()
    return _CEILING_TYPE_MAP.get(cleaned)


def find_missing_fields(project_info: dict) -> list[str]:
    """Return the list of required fields that are explicitly None.

    Uses ``is None`` checks (not truthiness) so that valid values like
    ``floors=1`` are never treated as missing.
    """
    parameters: dict[str, Any] = project_info.get("parameters") or {}
    missing: list[str] = []
    for field in _REQUIRED_ROOT_FIELDS:
        if project_info.get(field) is None:
            missing.append(field)
    for field in _REQUIRED_PARAMETER_FIELDS:
        if parameters.get(field) is None:
            missing.append(field)
    return missing


def validate_field_value(field: str, value: Any) -> str | None:
    """Check whether *value* is semantically valid for *field*.

    Returns an error message string if the value is invalid,
    or ``None`` if the value is acceptable.
    """
    if field in _INT_FIELD_RULES and value is not None:
        min_val, max_val, msg = _INT_FIELD_RULES[field]
        try:
            int_val = int(value)
            if not (min_val <= int_val <= max_val):
                return msg
        except (TypeError, ValueError):
            pass  # parse failure handled separately by the controller
    return None


def build_clarification_questions(missing_fields: list[str]) -> list[str]:
    return [_QUESTIONS.get(field, f"Please provide {field}.") for field in missing_fields]


def get_question_metadata(field: str) -> dict:
    """Return the SSE metadata dict for a given field.

    Includes ``input_type`` and, for dropdown/area-picker fields, the
    list of selectable options.
    """
    if field in _DROPDOWN_FIELDS:
        return {
            "input_type": "dropdown",
            "options": _DROPDOWN_FIELDS[field],
        }
    if field == "built_up_area":
        return {
            "input_type": "area_picker",
            "presets": [
                {"value": "750 sqft",  "label": "Under 1,000 sq ft"},
                {"value": "1250 sqft", "label": "1,000 – 1,500 sq ft"},
                {"value": "1750 sqft", "label": "1,500 – 2,000 sq ft"},
                {"value": "2250 sqft", "label": "2,000 – 2,500 sq ft"},
                {"value": "2750 sqft", "label": "2,500 – 3,000 sq ft"},
                {"value": "3500 sqft", "label": "3,000+ sq ft"},
            ],
            "allow_custom": True,
            "custom_units": ["sqft", "m2"],
        }
    return {"input_type": "text"}


def apply_defaults(project_info: dict) -> dict:
    """Fill non-MVED fields with Sri Lankan construction defaults.

    Only fills fields that are ``None`` or absent.  Each applied default
    is noted in ``project_info["applied_defaults"]`` so the transparency
    layer can report them and the confidence scorer can penalise them.
    """
    from core.logging.logger import get_logger  # local import to avoid circular
    logger = get_logger(__name__)

    parameters: dict = project_info.get("parameters") or {}
    applied: list[str] = []
    for field, default_value in _PARAMETER_DEFAULTS.items():
        if parameters.get(field) is None:
            parameters[field] = default_value
            applied.append(field)
            logger.warning(
                "apply_default field=%s value=%r  (no user input — using Sri Lankan norm)",
                field,
                default_value,
            )
    project_info["parameters"] = parameters
    if applied:
        existing = project_info.get("applied_defaults") or []
        project_info["applied_defaults"] = list(set(existing + applied))
    return project_info


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

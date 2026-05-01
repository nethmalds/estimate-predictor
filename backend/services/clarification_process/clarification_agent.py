from typing import Any


_REQUIRED_ROOT_FIELDS = [
    "floors",
]

# This estimation system is residential-only.
# Question order matches the order fields appear here:
#   1. floors  (root field)
#   2. bedrooms
#   3. bathrooms
#   4. built_up_area
#   5. finish_level
#   6. roof_type
#   7. ceiling_type
# structural_system, location, soil_condition, drainage_type, external_works_scope
# are NOT asked; they are filled silently via _PARAMETER_DEFAULTS.
_REQUIRED_PARAMETER_FIELDS_UNIVERSAL = [
    "bedrooms",
    "bathrooms",
    "built_up_area",
    "finish_level",
    "roof_type",
    "ceiling_type",
]

# No longer used — kept only for back-compat with any external callers.
_REQUIRED_PARAMETER_FIELDS_RESIDENTIAL: list[str] = []

# Back-compat alias.
_REQUIRED_PARAMETER_FIELDS = _REQUIRED_PARAMETER_FIELDS_UNIVERSAL

# Sri Lankan construction defaults — applied silently for non-MVED fields.
# These are never shown to the user as questions; they are logged at WARNING
# level in the transparency layer whenever they are actually used.
_PARAMETER_DEFAULTS: dict[str, str] = {
    "location": "Colombo",
    "soil_condition": "normal",
    "structural_system": "framed",
    "drainage_type": "septic_tank",
    "external_works_scope": "minimal",
}

# Fields whose questions must be answered via a dropdown widget in the frontend.
# Each entry maps the field name to its list of {value, label} options.
_DROPDOWN_FIELDS: dict[str, list[dict[str, str]]] = {
    "finish_level": [
        {"value": "standard",   "label": "Standard"},
        {"value": "semi-luxury","label": "Semi-Luxury"},
        {"value": "luxury",     "label": "Luxury"},
    ],
    "structural_system": [
        {"value": "framed",       "label": "Framed (RC Columns & Beams)"},
        {"value": "load_bearing", "label": "Load Bearing Masonry"},
        {"value": "hybrid",       "label": "Hybrid (Part Frame, Part Load Bearing)"},
    ],
    "roof_type": [
        {"value": "rc flat slab",   "label": "Flat Concrete Slab (RC)"},
        {"value": "clay tile",      "label": "Clay Tile Roof"},
        {"value": "asbestos sheet", "label": "Asbestos Sheet Roof"},
        {"value": "unknown",        "label": "Other / Unknown"},
    ],
    "ceiling_type": [
        {"value": "gypsum/mineral fibre", "label": "Gypsum / Mineral Fibre Board"},
        {"value": "lunumidella timber",   "label": "Lunumidella Timber"},
        {"value": "asbestos flat",        "label": "Asbestos Flat"},
        {"value": "unknown",              "label": "Other / Unknown"},
    ],
    "drainage_type": [
        {"value": "mains_sewer", "label": "Mains Sewer Connection"},
        {"value": "septic_tank", "label": "Septic Tank"},
        {"value": "soakpit",     "label": "Soakpit"},
        {"value": "none",        "label": "None / Not Applicable"},
    ],
    "external_works_scope": [
        {"value": "none",      "label": "None"},
        {"value": "minimal",   "label": "Minimal (Boundary Wall Only)"},
        {"value": "standard",  "label": "Standard (Boundary Wall + Gate + Paths)"},
        {"value": "extensive", "label": "Extensive (Full Landscaping & Paving)"},
    ],
}

_QUESTIONS = {
    "floors":               "How many floors (storeys) will the building have?",
    "built_up_area":        "What is the total built-up area? Select a range or enter a custom size.",
    "finish_level":         "What level of finishes are you looking for?",
    "structural_system":    "What structural system will be used for the building?",
    "roof_type":            "What type of roof will the building have?",
    "ceiling_type":         "What type of ceiling finish will be used?",
    "location":             "In which district or city in Sri Lanka is the project located?",
    "bedrooms":             "How many bedrooms are required?",
    "bathrooms":            "How many bathrooms are required?",
    "soil_condition":       "What is the soil condition at the site?",
    "drainage_type":        "What type of drainage or sewage system will be used?",
    "external_works_scope": "What is the scope of external works (boundary walls, paving, landscaping)?",
}

_CEILING_TYPE_MAP: dict[str, str] = {
    # Model canonical values — pass through directly
    "gypsum/mineral fibre":  "gypsum/mineral fibre",
    "lunumidella timber":    "lunumidella timber",
    "asbestos flat":         "asbestos flat",
    "unknown":               "unknown",
    # Common free-text inputs → nearest model class
    "gypsum":                "gypsum/mineral fibre",
    "gypsum board":          "gypsum/mineral fibre",
    "mineral fibre":         "gypsum/mineral fibre",
    "pvc":                   "gypsum/mineral fibre",
    "board":                 "gypsum/mineral fibre",
    "1":                     "gypsum/mineral fibre",
    "timber":                "lunumidella timber",
    "lunumidella":           "lunumidella timber",
    "wood":                  "lunumidella timber",
    "2":                     "lunumidella timber",
    "asbestos":              "asbestos flat",
    "asbestos sheet":        "asbestos flat",
    "3":                     "asbestos flat",
    "concrete":              "unknown",
    "none":                  "unknown",
    "4":                     "unknown",
    "":                      "unknown",
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
    """Return required fields that are still None.

    This system is residential-only. All seven fields are always checked.
    Uses ``is None`` so valid values like ``floors=1`` are never treated as missing.
    """
    parameters: dict[str, Any] = project_info.get("parameters") or {}
    missing: list[str] = []
    for field in _REQUIRED_ROOT_FIELDS:
        if project_info.get(field) is None:
            missing.append(field)
    for field in _REQUIRED_PARAMETER_FIELDS_UNIVERSAL:
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

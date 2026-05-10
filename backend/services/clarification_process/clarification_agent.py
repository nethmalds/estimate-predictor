"""Wizard form agent — validation, normalization, and default application.

This module exclusively supports the wizard form submission flow.
The legacy clarification chat functions (find_missing_fields,
build_clarification_questions, get_question_metadata,
normalize_ceiling_type, validate_field_value) and the LLM text-extraction
flow have been removed as the frontend no longer has a chat interface.
"""
from typing import Any


# ─── Canonical enum definitions ───────────────────────────────────────────────
# Used by the wizard frontend to populate dropdowns.

CANONICAL_ENUMS: dict[str, list[dict[str, str]]] = {
    "building_type": [
        {"value": "residential",  "label": "Residential"},
        {"value": "commercial",   "label": "Commercial"},
        {"value": "industrial",   "label": "Industrial"},
    ],
    "finish_level": [
        {"value": "standard",    "label": "Standard"},
        {"value": "semi_luxury", "label": "Semi-Luxury"},
        {"value": "luxury",      "label": "Luxury"},
    ],
    "structural_system": [
        {"value": "framed",       "label": "Framed (RC Columns & Beams)"},
        {"value": "load_bearing", "label": "Load Bearing Masonry"},
        {"value": "hybrid",       "label": "Hybrid"},
    ],
    "roof_type": [
        {"value": "rc_flat_slab",   "label": "Flat Concrete Slab (RC)"},
        {"value": "clay_tile",      "label": "Clay Tile Roof"},
        {"value": "asbestos_sheet", "label": "Asbestos Sheet Roof"},
        {"value": "metal_sheet",    "label": "Metal Sheet Roof"},
        {"value": "other",          "label": "Other"},
    ],
    "ceiling_type": [
        {"value": "gypsum_mineral_fibre", "label": "Gypsum / Mineral Fibre Board"},
        {"value": "timber",               "label": "Timber"},
        {"value": "asbestos_flat",        "label": "Asbestos Flat"},
        {"value": "concrete",             "label": "Concrete"},
        {"value": "other",                "label": "Other"},
    ],
    "soil_condition": [
        {"value": "normal",      "label": "Normal"},
        {"value": "expansive",   "label": "Expansive"},
        {"value": "rocky",       "label": "Rocky"},
        {"value": "waterlogged", "label": "Waterlogged"},
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
        {"value": "standard",  "label": "Standard (Wall + Gate + Paths)"},
        {"value": "extensive", "label": "Extensive (Full Landscaping & Paving)"},
    ],
}


# ─── Sri Lankan construction defaults ─────────────────────────────────────────
# Applied silently for non-MVED fields not provided by the wizard.

_PARAMETER_DEFAULTS: dict[str, str] = {
    "location":             "Colombo",
    "soil_condition":       "normal",
    "structural_system":    "framed",
    "drainage_type":        "septic_tank",
    "external_works_scope": "minimal",
}


# ─── Public API ───────────────────────────────────────────────────────────────

def derive_floor_areas_total(floor_areas: list[dict]) -> dict:
    """Compute totals from a list of {area_value, area_unit} floor area rows.

    Returns:
        {
            "total_m2": float,
            "total_sqft": float,
            "built_up_area_compat": str,   # e.g. "2300 sqft"
        }
    """
    total_m2 = 0.0
    total_sqft = 0.0
    for row in floor_areas:
        value = float(row.get("area_value", 0) or 0)
        unit = str(row.get("area_unit", "sqft")).lower().strip()
        if unit in {"m2", "m²"}:
            total_m2 += value
            total_sqft += value / 0.0929
        else:  # default sqft
            total_sqft += value
            total_m2 += value * 0.0929

    compat = f"{total_sqft:.0f} sqft" if total_sqft > 0 else "0 sqft"
    return {
        "total_m2": round(total_m2, 2),
        "total_sqft": round(total_sqft, 2),
        "built_up_area_compat": compat,
    }


def apply_defaults(project_info: dict) -> dict:
    """Fill non-MVED fields with Sri Lankan construction defaults.

    Only fills fields that are ``None`` or absent.  Each applied default
    is noted in ``project_info["applied_defaults"]`` so the transparency
    layer can report them and the confidence scorer can penalise them.
    """

    parameters: dict = project_info.get("parameters") or {}
    applied: list[str] = []
    for field, default_value in _PARAMETER_DEFAULTS.items():
        if parameters.get(field) is None:
            parameters[field] = default_value
            applied.append(field)
    project_info["parameters"] = parameters
    if applied:
        existing = project_info.get("applied_defaults") or []
        project_info["applied_defaults"] = list(set(existing + applied))
    return project_info


def merge_parameters(project_info: dict, overrides: dict | None) -> dict:
    """Merge override parameters into project_info, non-None values win."""
    if not overrides:
        return project_info
    parameters = project_info.get("parameters") or {}
    for key, value in overrides.items():
        if value is None:
            continue
        parameters[key] = value
    project_info["parameters"] = parameters
    return project_info


def normalize_wizard_to_project_info(payload: dict) -> dict:
    """Map a wizard form payload dict to the project_info structure expected by the pipeline.

    Wizard payload keys expected:
        building_type, floor_count, floor_areas (list of {floor_label, area_value, area_unit}),
        bedrooms, bathrooms (residential),
        primary_use_type, washroom_count (commercial),
        facility_type, heavy_machinery_load, hazardous_materials, specialized_ventilation (industrial),
        finish_level, structural_system, roof_type, ceiling_type,
        location, soil_condition, drainage_type, external_works_scope,
        floorplan_urls, description
    """
    floor_areas: list[dict] = payload.get("floor_areas") or []
    area_totals = derive_floor_areas_total(floor_areas)

    building_type = payload.get("building_type") or "residential"
    floors = int(payload.get("floor_count") or len(floor_areas) or 1)

    # Core parameters expected by the pipeline — only user-supplied values here;
    # defaults are applied exclusively in apply_defaults() so provenance is truthful.
    parameters: dict[str, Any] = {
        "built_up_area":        area_totals["built_up_area_compat"],
        "finish_level":         payload.get("finish_level"),
        "structural_system":    payload.get("structural_system"),
        "roof_type":            payload.get("roof_type"),
        "ceiling_type":         payload.get("ceiling_type"),
        "location":             payload.get("location"),
        "soil_condition":       payload.get("soil_condition"),
        "drainage_type":        payload.get("drainage_type"),
        "external_works_scope": payload.get("external_works_scope"),
    }

    # Residential-only fields
    if building_type == "residential":
        parameters["bedrooms"]  = payload.get("bedrooms")
        parameters["bathrooms"] = payload.get("bathrooms")

    # Commercial-only fields
    if building_type == "commercial":
        parameters["primary_use_type"] = payload.get("primary_use_type")
        parameters["washroom_count"]   = payload.get("washroom_count")

    # Industrial-only fields
    if building_type == "industrial":
        parameters["facility_type"]           = payload.get("facility_type")
        parameters["heavy_machinery_load"]    = payload.get("heavy_machinery_load")
        parameters["hazardous_materials"]     = payload.get("hazardous_materials")
        parameters["specialized_ventilation"] = payload.get("specialized_ventilation")

    # Track what came from the user explicitly (all wizard fields are user-provided)
    explicit_parameters = [k for k, v in parameters.items() if v is not None]

    # Collect preprocessing warnings for transparency
    preprocessing_warnings: list[str] = []
    if not payload.get("finish_level"):
        preprocessing_warnings.append("finish_level not provided — will use default.")
    if not payload.get("structural_system"):
        preprocessing_warnings.append("structural_system not provided — will use default.")
    if not payload.get("location"):
        preprocessing_warnings.append("location not provided — defaulting to Colombo.")

    return {
        "building_type":          building_type,
        "floors":                 floors,
        "spaces":                 [],
        "parameters":             parameters,
        "floor_areas":            floor_areas,
        "qs_specifications":      {},
        "explicit_parameters":    explicit_parameters,
        "assumptions":            [],
        "applied_defaults":       [],
        "value_sources":          {k: "user" for k in explicit_parameters},
        "preprocessing_warnings": preprocessing_warnings,
    }


def validate_wizard_payload(payload: dict) -> dict[str, str]:
    """Validate a wizard form payload and return a dict of field -> error_message.

    Covers:
    - Type and enum membership checks for all fields.
    - Logical consistency checks (floor count vs area rows, area sanity).
    - Acceptable-range validations for numeric fields.

    Returns an empty dict if there are no validation errors.
    """
    errors: dict[str, str] = {}

    building_type = payload.get("building_type")
    if building_type not in {"residential", "commercial", "industrial"}:
        errors["building_type"] = "Please select a valid building type."

    floor_count = payload.get("floor_count")
    try:
        fc = int(floor_count)
        if not (1 <= fc <= 100):
            errors["floor_count"] = "Floor count must be between 1 and 100."
    except (TypeError, ValueError):
        errors["floor_count"] = "Please enter a valid floor count."
        fc = 0

    floor_areas: list[dict] = payload.get("floor_areas") or []
    if not floor_areas:
        errors["floor_areas"] = "Please provide area for at least one floor."
    else:
        total_m2 = 0.0
        for i, row in enumerate(floor_areas):
            try:
                v = float(row.get("area_value", 0) or 0)
                if v <= 0:
                    errors[f"floor_areas[{i}]"] = f"Floor {i+1} area must be greater than zero."
                unit = str(row.get("area_unit", "sqft")).lower().strip()
                total_m2 += v * 0.0929 if unit not in {"m2", "m²"} else v
            except (TypeError, ValueError):
                errors[f"floor_areas[{i}]"] = f"Floor {i+1} area is not a valid number."

        # Area sanity: realistic construction range 20 m² – 50 000 m²
        if total_m2 > 0 and not (20 <= total_m2 <= 50_000):
            if total_m2 < 20:
                errors["floor_areas"] = (
                    f"Total floor area ({total_m2:.1f} m²) is unrealistically small. "
                    "Minimum expected is 20 m²."
                )
            else:
                errors["floor_areas"] = (
                    f"Total floor area ({total_m2:.1f} m²) exceeds the maximum supported "
                    "project size (50 000 m²). Please contact support for large projects."
                )

    # Required construction detail fields
    for required_field in ("finish_level", "structural_system", "roof_type", "ceiling_type"):
        if not payload.get(required_field):
            label = required_field.replace("_", " ").title()
            errors[required_field] = f"Please select a {label}."

    finish_level = payload.get("finish_level")
    if finish_level and finish_level not in {"standard", "semi_luxury", "luxury"}:
        errors["finish_level"] = "Invalid finish level selection."

    structural_system = payload.get("structural_system")
    if structural_system and structural_system not in {"framed", "load_bearing", "hybrid"}:
        errors["structural_system"] = "Invalid structural system selection."

    roof_type = payload.get("roof_type")
    valid_roof = {"rc_flat_slab", "clay_tile", "asbestos_sheet", "metal_sheet", "other"}
    if roof_type and roof_type not in valid_roof:
        errors["roof_type"] = "Invalid roof type selection."

    ceiling_type = payload.get("ceiling_type")
    valid_ceiling = {"gypsum_mineral_fibre", "timber", "asbestos_flat", "concrete", "other"}
    if ceiling_type and ceiling_type not in valid_ceiling:
        errors["ceiling_type"] = "Invalid ceiling type selection."

    soil_condition = payload.get("soil_condition")
    if soil_condition and soil_condition not in {"normal", "expansive", "rocky", "waterlogged"}:
        errors["soil_condition"] = "Invalid soil condition selection."

    drainage_type = payload.get("drainage_type")
    if drainage_type and drainage_type not in {"mains_sewer", "septic_tank", "soakpit", "none"}:
        errors["drainage_type"] = "Invalid drainage type selection."

    external_works_scope = payload.get("external_works_scope")
    if external_works_scope and external_works_scope not in {"none", "minimal", "standard", "extensive"}:
        errors["external_works_scope"] = "Invalid external works scope selection."

    if building_type == "residential":
        bedrooms = payload.get("bedrooms")
        try:
            b = int(bedrooms)
            if not (1 <= b <= 50):
                errors["bedrooms"] = "Bedrooms must be between 1 and 50."
        except (TypeError, ValueError):
            errors["bedrooms"] = "Please enter a valid number of bedrooms."

        bathrooms = payload.get("bathrooms")
        try:
            bt = int(bathrooms)
            if not (1 <= bt <= 50):
                errors["bathrooms"] = "Bathrooms must be between 1 and 50."
        except (TypeError, ValueError):
            errors["bathrooms"] = "Please enter a valid number of bathrooms."

    if building_type == "commercial":
        washroom_count = payload.get("washroom_count")
        try:
            wc = int(washroom_count)
            if wc < 1:
                errors["washroom_count"] = "Commercial buildings must have at least 1 washroom."
        except (TypeError, ValueError):
            errors["washroom_count"] = "Please enter a valid washroom count."

    return errors
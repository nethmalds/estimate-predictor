"""BOQ item validation — pre-RAG structural gate.

Called immediately after BOQ reconciliation (Stage 5a) before BSR retrieval,
to ensure the item list is structurally sound before expensive downstream
computations run.

Validation rule set (validate_boq_items — simple gate)
-------------------
1. List must be non-empty.
2. Each item must have a non-empty ``description``.
3. Each item must have a recognised (non-misc/empty) ``category``.
4. Each item must have a ``unit`` or ``preferred_unit`` field.
5. Each item must have a ``section`` field (non-empty, non-generic).
6. Each item must have a ``source`` provenance tag.
7. No duplicate descriptions (exact-match guard).

validate_generated_boq_items — richer post-reconciliation validator
--------------------------------------------------------------------
Uses a broader valid-category set (including miscellaneous), scope-conflict
detection, and completeness heuristics.  Returns errors + warnings.
"""

import re

_VALID_SOURCES: frozenset[str] = frozenset({
    "llm_baseline", "item_predictor", "llm_reconciled",
})
_GENERIC_SECTIONS: frozenset[str] = frozenset({
    "miscellaneous", "other", "misc", "general", "",
})

# Valid BSR work categories (broad set, includes miscellaneous)
_VALID_CATEGORIES: frozenset[str] = frozenset({
    "preliminary_and_general",
    "excavation_and_earthwork",
    "piling_and_substructure",
    "concrete_works",
    "formwork",
    "reinforcement",
    "brick_masonry",
    "plastering_and_rendering",
    "painting_and_finishes",
    "roofing_and_ceiling",
    "doors_windows_and_glazing",
    "flooring_and_tiling",
    "sanitary_and_plumbing",
    "electrical_and_mechanical",
    "external_and_civil_works",
    "demolition_and_removal",
    "testing_and_commissioning",
    "miscellaneous",
})


def validate_boq_items(items: list[dict]) -> dict:
    """Validate the structural integrity of a BOQ item list (pre-RAG gate).

    Returns
    -------
    dict
        ``{"is_valid": bool, "errors": list[str], "warnings": list[str]}``
    """
    errors: list[str] = []
    warnings: list[str] = []

    if not items:
        errors.append("BOQ item list is empty — no items to estimate.")
        return {"is_valid": False, "errors": errors, "warnings": warnings}

    seen_descriptions: set[str] = set()

    for i, item in enumerate(items):
        desc = (item.get("description") or "").strip()
        label = f"Item {i} ('{desc or '?'}')"

        # Rule 2 — description
        if not desc:
            errors.append(f"Item {i}: missing description.")
            continue

        # Rule 7 — duplicate guard
        desc_lower = desc.lower()
        if desc_lower in seen_descriptions:
            warnings.append(f"{label}: duplicate description detected.")
        seen_descriptions.add(desc_lower)

        # Rule 3 — category
        category = (item.get("category") or "").strip().lower()
        if not category or category in ("misc", "miscellaneous", "other"):
            errors.append(f"{label}: category is '{category or 'None'}' — must be a recognised BSR work category.")

        # Rule 4 — unit (prefer explicit unit, fall back to preferred_unit)
        unit = (item.get("unit") or item.get("preferred_unit") or "").strip()
        if not unit:
            errors.append(f"{label}: missing unit and preferred_unit.")

        # Rule 5 — section
        section = (item.get("section") or "").strip().lower()
        if section in _GENERIC_SECTIONS:
            warnings.append(f"{label}: section is '{section or 'None'}' — expected a specific BSR section.")

        # Rule 6 — source provenance
        source = (item.get("source") or "").strip()
        if source not in _VALID_SOURCES:
            warnings.append(
                f"{label}: source tag '{source}' is not a recognised provenance value "
                f"({', '.join(sorted(_VALID_SOURCES))})."
            )

    is_valid = len(errors) == 0
    return {"is_valid": is_valid, "errors": errors, "warnings": warnings}


# ---------------------------------------------------------------------------
# Richer post-reconciliation validator (used by tests and Phase 5 audit)
# ---------------------------------------------------------------------------

_SCOPE_CONFLICT_RULES: list[tuple] = [
    # (condition_fn, items_keyword, warning_message)
    # RC flat slab + asbestos roof items → likely scope conflict
    (
        lambda proj: (proj.get("parameters") or {}).get("roof_type", "") in ("rc_flat_slab", "flat_slab"),
        re.compile(r"\basbestos\b", re.IGNORECASE),
        "Asbestos roofing item detected but project roof type is RC flat slab — likely scope conflict.",
    ),
    # Normal soil + piling items → unusual combination
    (
        lambda proj: (proj.get("parameters") or {}).get("soil_condition", "") == "normal",
        re.compile(r"\bpil(ing|e|ed)\b", re.IGNORECASE),
        "Piling item detected but soil condition is 'normal' — verify whether deep foundations are required.",
    ),
    # Commercial project + bedroom items → domestic scope in commercial
    (
        lambda proj: proj.get("building_type", "") == "commercial",
        re.compile(r"\bbedroom\b", re.IGNORECASE),
        "Bedroom item detected in a commercial project — likely domestic scope conflict.",
    ),
    # Industrial project + decorative items → finish mismatch
    (
        lambda proj: proj.get("building_type", "") == "industrial",
        re.compile(r"\bdecorative\b", re.IGNORECASE),
        "Decorative finish item detected in an industrial project — verify finish specification.",
    ),
]


def validate_generated_boq_items(
    items: list[dict],
    project_info: dict,
) -> dict:
    """Richer post-reconciliation BOQ validator.

    Parameters
    ----------
    items:
        Reconciled BOQ item list from Stage 3 (gap-fill reconciliation).
    project_info:
        Normalised project_info dict used for scope-conflict detection.

    Returns
    -------
    dict
        ``{"is_valid": bool, "errors": list[str], "warnings": list[str]}``
    """
    errors: list[str] = []
    warnings: list[str] = []

    if not items:
        errors.append("BOQ item list is empty — no items to estimate.")
        return {"is_valid": False, "errors": errors, "warnings": warnings}

    # Completeness: at least one preliminary item expected
    has_prelim = any(
        (it.get("category") or "").lower() == "preliminary_and_general"
        for it in items
    )
    if not has_prelim:
        warnings.append(
            "No preliminary_and_general item found — a Preliminaries & General item "
            "is expected in every BOQ."
        )

    seen_descriptions: set[str] = set()

    for i, item in enumerate(items):
        desc = (item.get("description") or "").strip()
        label = f"Item {i} ('{desc or '?'}')"

        if not desc:
            errors.append(f"Item {i}: missing description.")
            continue

        # Duplicate guard
        desc_lower = desc.lower()
        if desc_lower in seen_descriptions:
            warnings.append(f"{label}: duplicate description detected.")
        seen_descriptions.add(desc_lower)

        # Category validation (broader set — miscellaneous is allowed here)
        category = (item.get("category") or "").strip().lower()
        if not category or category not in _VALID_CATEGORIES:
            errors.append(f"{label}: unrecognised category '{category or 'None'}'.")

        # Unit completeness (warning only — rate may come from BSR)
        preferred_unit = (item.get("preferred_unit") or item.get("unit") or "").strip()
        if not preferred_unit:
            warnings.append(f"{label}: missing preferred_unit — BSR matching may fail.")

        # Section completeness (warning only)
        section = (item.get("section") or "").strip()
        if not section:
            warnings.append(f"{label}: missing section — expected a specific BSR section heading.")

        # Scope conflict detection
        for condition_fn, pattern, message in _SCOPE_CONFLICT_RULES:
            if condition_fn(project_info) and pattern.search(desc):
                warnings.append(f"{label}: {message}")

    is_valid = len(errors) == 0
    return {"is_valid": is_valid, "errors": errors, "warnings": warnings}

"""BOQ item validation (Q2 fix — was a 2-line placeholder).

Called during Stage 8 before quantity take-off begins, to ensure the BOQ list
is structurally sound before expensive downstream computations run.
"""



def validate_boq_items(items: list[dict]) -> dict:
    """Validate the structural integrity of a BOQ item list.

    Checks performed:
    - List is not empty
    - Each item has a non-empty ``description``
    - Each item has a recognised ``category`` (not None/empty)
    - Each item has a ``unit`` field

    Returns
    -------
    dict
        ``{"is_valid": bool, "errors": list[str]}``
    """
    errors: list[str] = []

    if not items:
        errors.append("BOQ item list is empty — no items to estimate.")
        return {"is_valid": False, "errors": errors}

    for i, item in enumerate(items):
        desc = (item.get("description") or "").strip()
        if not desc:
            errors.append(f"Item {i}: missing description.")

        category = (item.get("category") or "").strip()
        if not category or category in ("misc", "miscellaneous"):
            errors.append(f"Item {i} ('{desc or '?'}'): category is '{category or 'None'}'.")

        unit = (item.get("unit") or "").strip()
        if not unit:
            errors.append(f"Item {i} ('{desc or '?'}'): missing unit.")

    is_valid = len(errors) == 0

    return {"is_valid": is_valid, "errors": errors}

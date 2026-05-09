"""BSR item matching logic - batch matching and contractual item classification."""
from __future__ import annotations

_CONTRACTUAL_KEYWORDS = {
    "performance security",
    "advance payment security",
    "advance payment bond",
    "advance bond",
    "lump sum",
}


def is_contractual_item(item: dict) -> bool:
    """Return True for financial/contractual items that cannot be BSR-matched."""
    desc = (item.get("description") or "").lower()
    cat  = (item.get("category") or "").lower()
    if cat == "preliminary_and_general":
        return True
    return any(kw in desc for kw in _CONTRACTUAL_KEYWORDS)


def match_boq_items_batch(items: list[dict], match_one_fn) -> list[dict]:
    """Match every BOQ item against BSR, skipping contractual items.

    Parameters
    ----------
    items:
        Raw BOQ items to match.
    match_one_fn:
        Callable[[str], dict] - single-item RAG match function, injected
        by service.py to avoid circular imports.
    """
    matched: list[dict] = []

    for item in items:
        description = item.get("description") or ""

        if is_contractual_item(item):
            merged = dict(item)
            merged.update({
                "bsr_item_no":      "CONTRACTUAL",
                "bsr_description":  None,
                "unit":             "item",
                "rate":             0.0,
                "match_confidence": 0.0,
                "match_type":       "contractual",
                "needs_rate_review": True,
            })
            matched.append(merged)
            continue

        bsr_match = match_one_fn(description)
        merged = dict(item)
        merged.update({
            "bsr_item_no":      bsr_match.get("item_no"),
            "bsr_description":  bsr_match.get("description"),
            "unit":             bsr_match.get("unit"),
            "rate":             bsr_match.get("rate") or 0.0,
            "match_confidence": bsr_match.get("confidence"),
            "match_type":       bsr_match.get("match_type", "no_match"),
            "needs_rate_review": bsr_match.get("needs_rate_review", False),
        })
        matched.append(merged)

    return matched

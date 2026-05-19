"""Floor-scope parsing helpers shared by item_gen_process and quantity_gen_process.

Lives in ``services.shared`` to avoid a ``quantity_gen → item_gen`` import cycle.
Both services need to (a) detect which floor a BOQ item description refers to and
(b) strip floor / size / orientation tokens to build a grouping signature.
"""
from __future__ import annotations

import re


# Floor-level tokens that identify per-floor BOQ items.
# Matches both spelled-out forms ("ground", "first") and abbreviations ("gf", "ff").
FLOOR_TOKENS = re.compile(
    r"\b(ground|first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth"
    r"|basement|roof|upper|lower|gf|ff|sf|tf)\b",
    re.IGNORECASE,
)

# Wall-thickness / orientation tokens stripped for grouping signatures.
# 9" / 225mm  → 9-inch (full) brick walls;  4.5" / 112mm → half-brick partitions.
_THICKNESS_TOKENS = re.compile(
    r'\b(?:9\s*(?:"|in|inch)?|4\.?5\s*(?:"|in|inch)?|225\s*mm?|112\s*mm?)\b',
    re.IGNORECASE,
)
_ORIENTATION_TOKENS = re.compile(
    r"\b(external|internal|partition|outer|inner)\b",
    re.IGNORECASE,
)

# Concrete grade tokens (kept here for reuse by the dedup helper).
GRADE_TOKENS = re.compile(r"\bgrade\s*\d+\b|\bc\d{2}\b", re.IGNORECASE)


_FLOOR_ALIASES: dict[str, str] = {
    "gf": "ground",
    "ff": "first",
    "sf": "second",
    "tf": "third",
}


def parse_floor_scope(description: str) -> str:
    """Return the floor-scope token for *description*.

    Returns one of ``ground``, ``first``, ``second`` … ``tenth``,
    ``basement``, ``roof``, ``upper``, ``lower``, or ``"all"`` when no
    floor token is present (whole-building item).

    Aliases (``gf``, ``ff``, ``sf``, ``tf``) are normalised to their
    canonical form.  When multiple distinct tokens appear in a single
    description the first match wins.
    """
    if not description:
        return "all"
    match = FLOOR_TOKENS.search(description)
    if not match:
        return "all"
    token = match.group(1).lower()
    return _FLOOR_ALIASES.get(token, token)


def strip_scope_tokens(description: str) -> str:
    """Remove floor / thickness / orientation tokens from *description*.

    Used to build a grouping signature so that "9\" external brickwork in
    ground floor" and "4.5\" internal brickwork in first floor" collapse
    to the same group key.
    """
    if not description:
        return ""
    text = FLOOR_TOKENS.sub(" ", description)
    text = _THICKNESS_TOKENS.sub(" ", text)
    text = _ORIENTATION_TOKENS.sub(" ", text)
    text = re.sub(r"[^a-z0-9 ]", " ", text.lower())
    text = re.sub(r"\s+", " ", text).strip()
    return text


def normalize_floor_label(floor_label: str, index: int = 0) -> str:
    """Normalise a user-supplied floor label to a canonical floor-scope token.

    Falls back to indexed naming (``ground``, ``first``, ``second`` …) when
    the label has no recognisable floor token — e.g. user types "Floor 1",
    "Top", or "Level A".

    Parameters
    ----------
    floor_label:
        Free-text label from the wizard payload.
    index:
        Zero-based position of the label in the ``floor_areas`` list.
        Used as a fallback when the label is ambiguous.
    """
    parsed = parse_floor_scope(floor_label or "")
    if parsed != "all":
        return parsed
    return _ordinal_for_index(index)


def _ordinal_for_index(index: int) -> str:
    """Return the canonical floor token for a zero-based floor index."""
    _ORDINALS = [
        "ground", "first", "second", "third", "fourth",
        "fifth", "sixth", "seventh", "eighth", "ninth", "tenth",
    ]
    if 0 <= index < len(_ORDINALS):
        return _ORDINALS[index]
    return f"level_{index}"

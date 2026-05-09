"""Item generation LLM client.

Handles all LLM calls that are specific to BOQ item generation:
  - generate_baseline_boq  : LLM Initial QS Pass seeded with Item Predictor hints
  - gap_fill_boq_items     : LLM comparison & gap-fill using predictor candidates
  - refine_boq_items       : Post-processing refinement of raw item lists
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from string import Template
from typing import Any

from infrastructure.integrations.openrouter_client import chat


_SYSTEM_PROMPT = (
    "You are a Quantity Surveyor specialising in Sri Lankan construction. "
    "Return JSON only with the exact schema. Use null for unknown values."
)

# Shared template directory — all prompt templates live in integrations
_TEMPLATE_DIR = (
    Path(__file__).resolve().parents[2]
    / "infrastructure" / "integrations" / "prompt_templates"
)
_TEMPLATE_CACHE: dict[str, str] = {}


def _load_template(name: str) -> str:
    if name in _TEMPLATE_CACHE:
        return _TEMPLATE_CACHE[name]
    content = (_TEMPLATE_DIR / name).read_text(encoding="utf-8")
    _TEMPLATE_CACHE[name] = content
    return content


def _render_template(name: str, **kwargs: str) -> str:
    return Template(_load_template(name)).safe_substitute(**kwargs)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_baseline_boq(
    project_info: dict,
    item_predictor_hints: list[str] | None = None,
) -> list[dict]:
    """LLM Initial QS Pass — generate a baseline BOQ item list from *project_info*.

    *item_predictor_hints* are the ML-predicted work-item descriptions.  They
    are embedded in the prompt so the LLM is seeded with the categories the
    Item Predictor expects before writing its own baseline list.
    """
    hints = item_predictor_hints or []
    prompt = _render_template(
        "generate_baseline_boq.txt",
        project_info_json=json.dumps(project_info, ensure_ascii=True),
        item_predictor_hints_json=json.dumps(hints, ensure_ascii=True),
    )
    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": prompt},
    ]
    content = chat(messages, stream=False)
    parsed = _safe_json_loads(content)
    items = parsed.get("items") if isinstance(parsed, dict) else None
    if not isinstance(items, list):
        return []
    result = _normalize_boq_item_list(items)
    return result


def gap_fill_boq_items(
    project_info: dict,
    baseline_items: list[dict],
    item_predictor_items: list[str],
) -> list[dict]:
    """Final BOQ reconciliation — returns the COMPLETE final item list.

    The LLM receives the baseline BOQ plus Item Predictor candidates and
    returns a single reconciled list after adding missing items, removing
    irrelevant or conflicting ones, deduplicating semantically, and
    normalizing all descriptions to BSR style.
    """
    prompt = _render_template(
        "gap_fill_boq_items.txt",
        project_info_json=json.dumps(project_info, ensure_ascii=True),
        baseline_items_json=json.dumps(baseline_items, ensure_ascii=True),
        item_predictor_items_json=json.dumps(item_predictor_items, ensure_ascii=True),
    )
    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": prompt},
    ]
    content = chat(messages, stream=False)
    parsed = _safe_json_loads(content)
    items = parsed.get("items") if isinstance(parsed, dict) else None
    if not isinstance(items, list):
        return baseline_items
    result = _normalize_boq_item_list(items)
    return result


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _safe_json_loads(text: str) -> dict:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{[\s\S]+\}", text)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass
    return {"_raw": text}


def _normalize_boq_item_list(items: list) -> list[dict]:
    normalized: list[dict] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        description = _coerce_value(item.get("description"))
        if not description:
            continue
        normalized.append({
            "description": description,
            "category": _coerce_value(item.get("category")) or "misc",
            "section": _coerce_value(item.get("section")) or "Miscellaneous",
        })
    return normalized


def _coerce_value(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str) and value.strip() == "":
        return None
    return str(value)

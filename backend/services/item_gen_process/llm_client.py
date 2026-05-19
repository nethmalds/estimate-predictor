"""Item generation LLM client.

Handles all LLM calls that are specific to BOQ item generation:
    - generate_baseline_boq: LLM Initial QS Pass using the resolved project info
    - gap_fill_boq_items: LLM refinement using baseline + predictor candidates
"""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from string import Template
from typing import Any

from infrastructure.integrations.ollama_client import chat

logger = logging.getLogger(__name__)


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
) -> list[dict]:
    """LLM Initial QS Pass — generate a baseline BOQ item list from *project_info*.

    Runs independently of the Item Predictor so the LLM produces an
    unbiased QS assessment.  The Item Predictor runs afterwards as a
    separate gap-suggestion step (Stage 2 in the aligned flow).
    """
    building_type = project_info.get("building_type", "residential").lower()
    if building_type not in ["residential", "commercial", "industrial"]:
        building_type = "residential"
        
    template_name = f"generate_baseline_boq_{building_type}.txt"
    
    prompt = _render_template(
        template_name,
        project_info_json=json.dumps(project_info, ensure_ascii=True),
    )
    return _execute_boq_generation(prompt, "baseline")


def gap_fill_boq_items(
    project_info: dict,
    baseline_items: list[dict],
    item_predictor_items: list[str],
) -> list[dict]:
    """Refine the baseline BOQ using predictor candidates and project constraints.

    The LLM compares baseline items and predictor candidates, then returns
    the final refined BOQ list for the project. If refinement fails or
    returns empty, this function falls back to the baseline list.
    """
    building_type = project_info.get("building_type", "residential").lower()
    if building_type not in ["residential", "commercial", "industrial"]:
        building_type = "residential"
        
    template_name = f"refine_boq_items_{building_type}.txt"

    baseline_payload: list[dict[str, str]] = []
    for item in baseline_items:
        if not isinstance(item, dict):
            continue
        description = item.get("description")
        if not description:
            continue
        baseline_payload.append({
            "description": str(description),
            "category": str(item.get("category") or "misc"),
            "section": str(item.get("section") or "Miscellaneous"),
        })

    prompt = _render_template(
        template_name,
        project_info_json=json.dumps(project_info, ensure_ascii=True),
        baseline_items_json=json.dumps(baseline_payload, ensure_ascii=True),
        item_predictor_items_json=json.dumps(item_predictor_items, ensure_ascii=True),
    )
    refined_items = _execute_boq_generation(
        prompt,
        "refine",
        fallback_items=baseline_items,
    )

    if not refined_items:
        return baseline_items

    return refined_items


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _execute_boq_generation(
    prompt: str,
    log_label: str,
    fallback_items: list[dict] | None = None,
) -> list[dict]:
    import time
    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": prompt},
    ]
    # High-thinking options: low temperature for analytical precision,
    # large context window so the model can reason over the full prompt.
    _reasoning_options = {
        "temperature": 0.1,
        "num_ctx": 8192,
        "top_p": 0.9,
    }
    start_time = time.time()
    content = chat(messages, stream=True, options=_reasoning_options)
    elapsed = time.time() - start_time
    logger.info("LLM %s BOQ generation took: %.2f seconds", log_label, elapsed)
    
    parsed = _safe_json_loads(content)
    items = parsed.get("items") if isinstance(parsed, dict) else None
    
    if not isinstance(items, list):
        return fallback_items if fallback_items is not None else []
        
    return _normalize_boq_item_list(items)


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

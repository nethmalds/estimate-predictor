import json
import re
from pathlib import Path
from string import Template
from typing import Any

from infrastructure.integrations.ollama_client import chat


_SYSTEM_PROMPT = (
    "You are an information extraction engine for construction projects. "
    "Return JSON only with the exact schema. Use null for unknown values."
)


_SCHEMA_HINT = {
    "building_type": "string or null",
    "floors": "integer or null",
    "spaces": "array of strings",
    "parameters": {
        "bedrooms": "integer or null",
        "bathrooms": "integer or null",
        "built_up_area": "string or null",
        "finish_level": "string or null",
        "roof_type": "string or null",
        "ceiling_type": "string or null",
    },
    "explicit_parameters": "array of strings",
    "assumptions": "array of strings",
}

_TEMPLATE_DIR = Path(__file__).resolve().parent / "prompt_templates"
_TEMPLATE_CACHE: dict[str, str] = {}


def _load_template(name: str) -> str:
    if name in _TEMPLATE_CACHE:
        return _TEMPLATE_CACHE[name]
    template_path = _TEMPLATE_DIR / name
    content = template_path.read_text(encoding="utf-8")
    _TEMPLATE_CACHE[name] = content
    return content


def _render_template(name: str, **kwargs: str) -> str:
    raw = _load_template(name)
    return Template(raw).safe_substitute(**kwargs)


def extract_project_info(description: str) -> dict:
    prompt = _render_template("extract_project_info.txt", description=description)
    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": prompt},
    ]
    content = chat(messages, stream=False)
    parsed = _safe_json_loads(content)
    return _normalize_project_info(parsed)


def check_requirements(description: str) -> dict:
    prompt = _render_template("check_requirements.txt", description=description)
    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": prompt},
    ]
    content = chat(messages, stream=False)
    parsed = _safe_json_loads(content)
    return _normalize_requirements_check(parsed)


def extract_project_info_with_clarifications(
    description: str,
    clarifications: dict | str,
) -> dict:
    clarifications_text = (
        json.dumps(clarifications, ensure_ascii=True)
        if isinstance(clarifications, dict)
        else str(clarifications)
    )
    prompt = _render_template(
        "extract_with_clarifications.txt",
        description=description,
        clarifications=clarifications_text,
    )
    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": prompt},
    ]
    content = chat(messages, stream=False)
    parsed = _safe_json_loads(content)
    return _normalize_project_info(parsed)


def refine_boq_items(project_info: dict, items: list[dict]) -> list[dict]:
    payload = json.dumps(
        {
            "project_info": project_info,
            "items": items,
        },
        ensure_ascii=True,
    )
    prompt = _render_template("refine_boq_items.txt", payload=payload)
    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": prompt},
    ]
    content = chat(messages, stream=False)
    parsed = _safe_json_loads(content)
    return _normalize_refined_boq(parsed)


def generate_baseline_boq(project_info: dict) -> list[dict]:
    """LLM Initial QS Pass — generate a baseline BOQ item list from project info."""
    project_info_json = json.dumps(project_info, ensure_ascii=True)
    prompt = _render_template("generate_baseline_boq.txt", project_info_json=project_info_json)
    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": prompt},
    ]
    content = chat(messages, stream=False)
    parsed = _safe_json_loads(content)
    items = parsed.get("items") if isinstance(parsed, dict) else None
    if not isinstance(items, list):
        return []
    return _normalize_boq_item_list(items)


def gap_fill_boq_items(
    project_info: dict,
    baseline_items: list[dict],
    item_predictor_items: list[str],
) -> list[dict]:
    """LLM Comparison & Gap Fill — add ONLY missing relevant items from Item Predictor."""
    project_info_json = json.dumps(project_info, ensure_ascii=True)
    baseline_json = json.dumps(baseline_items, ensure_ascii=True)
    item_predictor_json = json.dumps(item_predictor_items, ensure_ascii=True)
    prompt = _render_template(
        "gap_fill_boq_items.txt",
        project_info_json=project_info_json,
        baseline_items_json=baseline_json,
        item_predictor_items_json=item_predictor_json,
    )
    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": prompt},
    ]
    content = chat(messages, stream=False)
    parsed = _safe_json_loads(content)
    added = parsed.get("added_items") if isinstance(parsed, dict) else None
    if not isinstance(added, list):
        return []
    return _normalize_boq_item_list(added)


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


def _normalize_project_info(data: dict) -> dict:
    info = {
        "building_type": _coerce_value(data.get("building_type")) or "residential",
        "floors": _coerce_int(data.get("floors")),
        "spaces": _coerce_list(data.get("spaces")),
        "parameters": _normalize_parameters(data.get("parameters") or {}),
        "explicit_parameters": _coerce_list(data.get("explicit_parameters")),
        "assumptions": _coerce_list(data.get("assumptions")),
    }

    if "_raw" in data:
        info["_raw_llm_response"] = data["_raw"]
    info["schema_hint"] = _SCHEMA_HINT
    return info


def _normalize_refined_boq(data: dict) -> list[dict]:
    items = data.get("items") if isinstance(data, dict) else None
    if not isinstance(items, list):
        return []

    normalized: list[dict] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        description = _coerce_value(item.get("description"))
        if not description:
            continue
        normalized.append(
            {
                "description": description,
                "category": _coerce_value(item.get("category")) or "misc",
                "section": _coerce_value(item.get("section")) or "Miscellaneous",
            }
        )
    return normalized


def _normalize_boq_item_list(items: list) -> list[dict]:
    """Shared normaliser for any LLM-returned list of BOQ item dicts."""
    normalized: list[dict] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        description = _coerce_value(item.get("description"))
        if not description:
            continue
        normalized.append(
            {
                "description": description,
                "category": _coerce_value(item.get("category")) or "misc",
                "section": _coerce_value(item.get("section")) or "Miscellaneous",
            }
        )
    return normalized


def _normalize_requirements_check(data: dict) -> dict:
    missing_fields = _coerce_list(data.get("missing_fields"))
    questions = _coerce_list(data.get("questions"))
    requirements_satisfied = bool(data.get("requirements_satisfied"))
    if missing_fields:
        requirements_satisfied = False
    return {
        "requirements_satisfied": requirements_satisfied,
        "missing_fields": missing_fields,
        "questions": questions,
    }


def _normalize_parameters(parameters: dict[str, Any]) -> dict:
    return {
        "bedrooms": _coerce_int(parameters.get("bedrooms")),
        "bathrooms": _coerce_int(parameters.get("bathrooms")),
        "built_up_area": _coerce_value(parameters.get("built_up_area")),
        "finish_level": _coerce_value(parameters.get("finish_level")),
        "roof_type": _coerce_value(parameters.get("roof_type")),
        "ceiling_type": _coerce_value(parameters.get("ceiling_type")),
    }


def _coerce_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if item is not None]
    if value is None:
        return []
    return [str(value)]


def _coerce_value(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str) and value.strip() == "":
        return None
    return str(value)


def _coerce_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None

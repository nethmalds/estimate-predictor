import json
import re
from pathlib import Path
from string import Template
from typing import Any

from core.logging.logger import get_logger
from infrastructure.integrations.openrouter_client import chat

logger = get_logger(__name__)


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

_TEMPLATE_DIR = (
    Path(__file__).resolve().parents[2]
    / "infrastructure" / "integrations" / "prompt_templates"
)
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
    logger.info("llm_call fn=extract_project_info desc_len=%d", len(description))
    prompt = _render_template("extract_project_info.txt", description=description)
    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": prompt},
    ]
    content = chat(messages, stream=False)
    parsed = _safe_json_loads(content)
    result = _normalize_project_info(parsed)
    logger.info("llm_call fn=extract_project_info building_type=%s floors=%s", result.get("building_type"), result.get("floors"))
    return result


def check_requirements(description: str) -> dict:
    logger.info("llm_call fn=check_requirements")
    prompt = _render_template("check_requirements.txt", description=description)
    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": prompt},
    ]
    content = chat(messages, stream=False)
    parsed = _safe_json_loads(content)
    result = _normalize_requirements_check(parsed)
    logger.info(
        "llm_call fn=check_requirements satisfied=%s missing_count=%d",
        result.get("requirements_satisfied"),
        len(result.get("missing_fields") or []),
    )
    return result


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

import json
import re
from typing import Any

from integrations.ollama_client import chat


_SYSTEM_PROMPT = (
    "You are an information extraction engine for construction projects. "
    "Return JSON only with the exact schema. Use null for unknown values."
)


_SCHEMA_HINT = {
    "building_type": "string or null",
    "floors": "integer or null",
    "spaces": "array of strings",
    "parameters": {
        "built_up_area": "string or null",
        "finish_level": "string or null",
        "structural_system": "string or null",
        "roof_type": "string or null",
        "location": "string or null",
        "soil_condition": "string or null",
        "drainage_type": "string or null",
        "external_works_scope": "string or null",
    },
    "explicit_parameters": "array of strings",
    "assumptions": "array of strings",
}


def extract_project_info(description: str) -> dict:
    prompt = (
        "Extract project details from the user description. "
        "Return only JSON with keys: building_type, floors, spaces, parameters, explicit_parameters, assumptions. "
        "The parameters object must contain built_up_area, finish_level, structural_system, roof_type, "
        "location, soil_condition, drainage_type, external_works_scope."
    )
    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": prompt + "\n\nDescription:\n" + description},
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
        "building_type": _coerce_value(data.get("building_type")),
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


def _normalize_parameters(parameters: dict[str, Any]) -> dict:
    return {
        "built_up_area": _coerce_value(parameters.get("built_up_area")),
        "finish_level": _coerce_value(parameters.get("finish_level")),
        "structural_system": _coerce_value(parameters.get("structural_system")),
        "roof_type": _coerce_value(parameters.get("roof_type")),
        "location": _coerce_value(parameters.get("location")),
        "soil_condition": _coerce_value(parameters.get("soil_condition")),
        "drainage_type": _coerce_value(parameters.get("drainage_type")),
        "external_works_scope": _coerce_value(parameters.get("external_works_scope")),
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

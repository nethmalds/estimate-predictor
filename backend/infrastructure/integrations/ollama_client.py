from typing import Iterable

from ollama import Client

from core.config.settings import settings


_DEFAULT_MODEL = "glm-5:cloud"
_client: Client | None = None


def _get_client() -> Client:
    global _client
    if _client is None:
        host = settings.ollama_host or "http://localhost:11434"
        api_key = settings.ollama_api_key
        headers = {}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        _client = Client(host=host, headers=headers)
    return _client


def _mock_fallback(messages: list[dict]) -> str:
    prompt = str(messages)
    if "requirements_satisfied" in prompt:
        return '{"requirements_satisfied": false, "missing_fields": [], "questions": []}'
    if "building_type" in prompt and "explicit_parameters" in prompt:
        return '{"building_type": "residential", "floors": 2, "spaces": ["living room"], "parameters": {"bedrooms": 3, "bathrooms": 2, "built_up_area": "2000", "finish_level": "standard", "roof_type": "flat", "ceiling_type": "gypsum"}, "explicit_parameters": [], "assumptions": []}'
    return '[{"description": "Mocked BOQ Item", "unit": "m2", "quantity": 100}]'

def chat(messages: list[dict], model: str | None = None, stream: bool = False) -> str:
    client = _get_client()
    model_name = model or settings.ollama_model or _DEFAULT_MODEL
    try:
        response = client.chat(model_name, messages=messages, stream=stream)
        if stream:
            return _consume_stream(response)
        return _extract_message_content(response)
    except Exception as exc:
        import os
        from core.logging.logger import get_logger
        logger = get_logger(__name__)
        if os.getenv("ENV", "development") == "development":
            logger.warning(f"LLM API failed. Using mock fallback. Error: {exc}")
            return _mock_fallback(messages)
        raise exc

def _consume_stream(parts: Iterable) -> str:
    chunks: list[str] = []
    for part in parts:
        chunks.append(_extract_message_content(part))
    return "".join(chunks)

def _extract_message_content(response) -> str:
    if isinstance(response, dict):
        message = response.get("message") or {}
        return message.get("content", "") or ""
    message = getattr(response, "message", None)
    if message is None:
        return ""
    return getattr(message, "content", "") or ""

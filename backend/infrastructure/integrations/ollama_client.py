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


def chat(messages: list[dict], model: str | None = None, stream: bool = False) -> str:
    client = _get_client()
    model_name = model or settings.ollama_model or _DEFAULT_MODEL
    response = client.chat(model_name, messages=messages, stream=stream)
    if stream:
        return _consume_stream(response)
    return _extract_message_content(response)


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

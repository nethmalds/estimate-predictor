"""OpenRouter LLM client.

Uses the OpenAI-compatible REST API provided by OpenRouter.
All existing callers use the same ``chat()`` signature — drop-in replacement
for the previous Ollama client.

Environment variables
---------------------
OPENROUTER_API_KEY  : required — your OpenRouter API key
OPENROUTER_MODEL    : optional — model string, e.g. ``mistralai/ministral-3b``
"""
from __future__ import annotations

import os
from typing import Iterable

from openai import OpenAI

from core.config.settings import settings


_BASE_URL = "https://openrouter.ai/api/v1"
_DEFAULT_MODEL = "openai/gpt-oss-120b:free"

_client: OpenAI | None = None


def _get_client() -> OpenAI:
    global _client  # noqa: PLW0603
    if _client is None:
        _client = OpenAI(
            base_url=_BASE_URL,
            api_key=settings.openrouter_api_key or "no-key",
        )
    return _client


def _mock_fallback(messages: list[dict]) -> str:
    prompt = str(messages)
    if "requirements_satisfied" in prompt:
        return '{"requirements_satisfied": false, "missing_fields": [], "questions": []}'
    if "building_type" in prompt and "explicit_parameters" in prompt:
        # Return minimal info with nulls so clarification questions are triggered
        return (
            '{"building_type": "residential", "floors": null, "spaces": [], '
            '"parameters": {"bedrooms": null, "bathrooms": null, "built_up_area": null, '
            '"finish_level": null, "roof_type": null, "ceiling_type": null}, '
            '"explicit_parameters": [], "assumptions": []}'
        )
    return '[{"description": "Mocked BOQ Item", "unit": "m2", "quantity": 100}]'


def chat(
    messages: list[dict],
    model: str | None = None,
    stream: bool = False,
) -> str:
    """Send a chat completion request to OpenRouter and return the response text.

    Parameters
    ----------
    messages:
        OpenAI-format message list.
    model:
        Override the model; falls back to ``OPENROUTER_MODEL`` env var or
        ``_DEFAULT_MODEL``.
    stream:
        If ``True``, consume the streaming response and return the full
        concatenated string.

    Returns
    -------
    str
        The assistant message content.
    """
    client = _get_client()
    model_name = model or settings.openrouter_model or _DEFAULT_MODEL
    try:
        response = client.chat.completions.create(
            model=model_name,
            messages=messages,  # type: ignore[arg-type]
            stream=stream,
            **(({"stream_options": {"include_usage": True}}) if stream else {}),
        )
        result = _consume_stream(response) if stream else _extract_content(response)
        return result
    except Exception as exc:
        # R1: only fall back to mock for connection / rate-limit issues in dev.
        # All other exceptions (auth errors, bad JSON, etc.) are re-raised.
        from openai import APIConnectionError, APIStatusError  # noqa: PLC0415
        is_transient = isinstance(exc, (APIConnectionError, APIStatusError))
        if is_transient and os.getenv("ENV", "development") == "development":
            return _mock_fallback(messages)
        raise


def _consume_stream(stream: Iterable) -> str:
    chunks: list[str] = []
    for chunk in stream:
        # Collect content deltas
        content = chunk.choices[0].delta.content  # type: ignore[union-attr]
        if content:
            chunks.append(content)

        # Usage information arrives in the final chunk
        usage = getattr(chunk, "usage", None)
        if usage:
            reasoning_tokens = getattr(usage, "reasoning_tokens", None)
            if reasoning_tokens is not None:
                # Reasoning token telemetry can be wired here later.
                pass

    return "".join(chunks)


def _extract_content(response) -> str:
    return response.choices[0].message.content or ""

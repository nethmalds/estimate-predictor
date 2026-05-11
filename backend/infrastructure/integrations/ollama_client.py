"""Ollama cloud LLM client.

Uses the official ``ollama`` Python package and keeps the existing
``chat()`` signature expected by the BOQ generation pipeline.
"""
from __future__ import annotations

import os

from ollama import Client

from core.config.settings import settings


_DEFAULT_MODEL = "gpt-oss:120b-cloud"
_client: Client | None = None


def _get_client() -> Client:
    global _client  # noqa: PLW0603
    if _client is None:
        headers: dict[str, str] = {}
        api_key = os.getenv("OLLAMA_API_KEY") or settings.ollama_api_key
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        host = os.getenv("OLLAMA_HOST") or "https://ollama.com"
        _client = Client(host=host, headers=headers or None)
    return _client


def _mock_fallback(messages: list[dict]) -> str:
    prompt = str(messages)
    if "requirements_satisfied" in prompt:
        return '{"requirements_satisfied": false, "missing_fields": [], "questions": []}'
    if "building_type" in prompt and "explicit_parameters" in prompt:
        return (
            '{"building_type": "residential", "floors": null, "spaces": [], '
            '"parameters": {"bedrooms": null, "bathrooms": null, "built_up_area": null, '
            '"finish_level": null, "roof_type": null, "ceiling_type": null}, '
            '"explicit_parameters": [], "assumptions": []}'
        )
    # Default: return BOQ items in the {"items": [...]} dict schema expected by _execute_boq_generation
    return (
        '{"items": ['
        '{"description": "Excavation for foundations", "category": "excavation_and_earthwork", "section": "Excavation & Earthwork"},'
        '{"description": "Mass concrete in foundations", "category": "piling_and_substructure", "section": "Piling & Substructure"},'
        '{"description": "RC columns and beams", "category": "concrete_works", "section": "Concrete Works"},'
        '{"description": "RC roof slab", "category": "roofing_and_ceiling", "section": "Roofing & Ceiling"},'
        '{"description": "Brick masonry walls 225mm", "category": "brick_masonry", "section": "Brick Masonry"},'
        '{"description": "Formwork to slabs and beams", "category": "formwork", "section": "Formwork"},'
        '{"description": "High tensile reinforcement", "category": "reinforcement", "section": "Reinforcement"},'
        '{"description": "Plastering to internal walls", "category": "plastering_and_rendering", "section": "Plastering & Rendering"},'
        '{"description": "Ceramic floor tiles 600x600", "category": "flooring_and_tiling", "section": "Flooring & Tiling"},'
        '{"description": "Gypsum board ceiling", "category": "roofing_and_ceiling", "section": "Roofing & Ceiling"},'
        '{"description": "Timber internal door", "category": "doors_windows_and_glazing", "section": "Doors, Windows & Glazing"},'
        '{"description": "Aluminium sliding window", "category": "doors_windows_and_glazing", "section": "Doors, Windows & Glazing"},'
        '{"description": "Emulsion paint to walls and ceiling", "category": "painting_and_finishes", "section": "Painting & Finishes"},'
        '{"description": "Electrical wiring and light fittings", "category": "electrical_and_mechanical", "section": "Electrical & Mechanical"},'
        '{"description": "Sanitary ware and plumbing installation", "category": "sanitary_and_plumbing", "section": "Sanitary & Plumbing"},'
        '{"description": "Water supply pipework", "category": "sanitary_and_plumbing", "section": "Sanitary & Plumbing"},'
        '{"description": "Preliminary and general items", "category": "preliminary_and_general", "section": "Preliminary & General"}'
        ']}'
    )


def chat(
    messages: list[dict],
    model: str | None = None,
    stream: bool = False,
) -> str:
    """Send a chat completion request to Ollama cloud and return the response text."""
    client = _get_client()
    model_name = model or os.getenv("OLLAMA_MODEL") or settings.ollama_model or _DEFAULT_MODEL

    try:
        response = client.chat(
            model=model_name,
            messages=messages,
            stream=stream,
        )
        return _consume_stream(response) if stream else _extract_content(response)
    except Exception as exc:  # noqa: BLE001
        if os.getenv("ENV", "development") == "development":
            return _mock_fallback(messages)
        raise exc


def _consume_stream(response) -> str:
    chunks: list[str] = []
    for chunk in response:
        content = _extract_message_content(chunk)
        if content:
            chunks.append(content)
    return "".join(chunks)


def _extract_content(response) -> str:
    try:
        return _extract_message_content(response)
    except Exception:
        return ""


def _extract_message_content(response) -> str:
    if isinstance(response, dict):
        message = response.get("message") or {}
    else:
        message = getattr(response, "message", None) or {}

    if isinstance(message, dict):
        return message.get("content") or ""
    return getattr(message, "content", "") or ""
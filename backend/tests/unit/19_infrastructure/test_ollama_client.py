"""Unit tests for ollama_client.py."""

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

_BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from infrastructure.integrations import ollama_client  # noqa: E402


@pytest.fixture(autouse=True)
def reset_cached_client(monkeypatch):
    monkeypatch.setattr(ollama_client, "_client", None)
    yield
    monkeypatch.setattr(ollama_client, "_client", None)


def _response(content: str) -> SimpleNamespace:
    return SimpleNamespace(message=SimpleNamespace(content=content))


class TestGetClient:
    def test_get_client_uses_default_host_and_bearer_auth(self, monkeypatch):
        created_clients: list[SimpleNamespace] = []

        def fake_client(*, host, headers=None):
            client = SimpleNamespace(host=host, headers=headers)
            created_clients.append(client)
            return client

        monkeypatch.setenv("OLLAMA_API_KEY", "test-token")
        monkeypatch.delenv("OLLAMA_HOST", raising=False)
        monkeypatch.setattr(ollama_client, "Client", fake_client)

        first_client = ollama_client._get_client()
        second_client = ollama_client._get_client()

        assert first_client is second_client
        assert len(created_clients) == 1
        assert created_clients[0].host == "https://ollama.com"
        assert created_clients[0].headers == {"Authorization": "Bearer test-token"}


class TestChat:
    def test_chat_forwards_simple_request_without_options(self, monkeypatch):
        messages = [{"role": "user", "content": "Why is the sky blue?"}]
        fake_client = SimpleNamespace(
            chat=MagicMock(return_value=_response("Because of Rayleigh scattering."))
        )

        monkeypatch.setattr(ollama_client, "_get_client", lambda: fake_client)
        monkeypatch.setenv("OLLAMA_MODEL", "gpt-oss:120b")

        result = ollama_client.chat(messages=messages, stream=False)

        assert result == "Because of Rayleigh scattering."
        kwargs = fake_client.chat.call_args.kwargs
        assert kwargs["model"] == "gpt-oss:120b"
        assert kwargs["messages"] == messages
        assert kwargs["stream"] is False
        assert "options" not in kwargs

    def test_chat_concatenates_streamed_message_parts(self, monkeypatch):
        messages = [{"role": "user", "content": "Why is the sky blue?"}]
        fake_client = SimpleNamespace(
            chat=MagicMock(return_value=[
                _response("Because "),
                _response("of Rayleigh "),
                _response("scattering."),
            ])
        )

        monkeypatch.setattr(ollama_client, "_get_client", lambda: fake_client)
        monkeypatch.setenv("OLLAMA_MODEL", "gpt-oss:120b")

        result = ollama_client.chat(messages=messages, stream=True)

        assert result == "Because of Rayleigh scattering."

    def test_chat_returns_mock_fallback_in_development(self, monkeypatch):
        fake_client = SimpleNamespace(chat=MagicMock(side_effect=RuntimeError("boom")))

        monkeypatch.setattr(ollama_client, "_get_client", lambda: fake_client)
        monkeypatch.setenv("ENV", "development")

        result = ollama_client.chat(messages=[{"role": "user", "content": "Hello"}])

        assert '"items"' in result
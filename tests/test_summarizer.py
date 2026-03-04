"""Tests for src/summarizer.py – Ollama summarisation."""

from unittest.mock import MagicMock, patch

import pytest

from src.summarizer import _SYSTEM_PROMPT, summarize


def test_summarize_calls_ollama_chat(monkeypatch):
    """summarize() calls ollama.Client.chat with the system prompt and transcript."""
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://localhost:11434")
    monkeypatch.setenv("OLLAMA_MODEL", "mistral")

    fake_response = MagicMock()
    fake_response.message.content = "  ## Session Overview\nGreat session!  "

    mock_client = MagicMock()
    mock_client.chat.return_value = fake_response

    with patch("src.summarizer.ollama.Client", return_value=mock_client) as mock_cls:
        result = summarize("The party fought a dragon.")

    # Client instantiated with the correct host
    mock_cls.assert_called_once_with(host="http://localhost:11434")

    # chat called with the right model and messages
    call_kwargs = mock_client.chat.call_args[1]
    assert call_kwargs["model"] == "mistral"
    messages = call_kwargs["messages"]
    assert messages[0]["role"] == "system"
    assert messages[0]["content"] == _SYSTEM_PROMPT
    assert messages[1]["role"] == "user"
    assert "The party fought a dragon." in messages[1]["content"]

    # Leading/trailing whitespace stripped
    assert result == "## Session Overview\nGreat session!"


def test_summarize_uses_env_vars(monkeypatch):
    """summarize() picks up OLLAMA_BASE_URL and OLLAMA_MODEL from the environment."""
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://192.168.1.100:11434")
    monkeypatch.setenv("OLLAMA_MODEL", "llama3")

    fake_response = MagicMock()
    fake_response.message.content = "Summary"

    mock_client = MagicMock()
    mock_client.chat.return_value = fake_response

    with patch("src.summarizer.ollama.Client", return_value=mock_client) as mock_cls:
        summarize("transcript")

    mock_cls.assert_called_once_with(host="http://192.168.1.100:11434")
    assert mock_client.chat.call_args[1]["model"] == "llama3"


def test_summarize_default_env(monkeypatch):
    """Default values are used when env vars are absent."""
    monkeypatch.delenv("OLLAMA_BASE_URL", raising=False)
    monkeypatch.delenv("OLLAMA_MODEL", raising=False)

    fake_response = MagicMock()
    fake_response.message.content = "ok"

    mock_client = MagicMock()
    mock_client.chat.return_value = fake_response

    with patch("src.summarizer.ollama.Client", return_value=mock_client) as mock_cls:
        summarize("x")

    mock_cls.assert_called_once_with(host="http://localhost:11434")
    assert mock_client.chat.call_args[1]["model"] == "mistral"


def test_summarize_propagates_ollama_error(monkeypatch):
    """Exceptions from Ollama are propagated to the caller."""
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://localhost:11434")
    monkeypatch.setenv("OLLAMA_MODEL", "mistral")

    mock_client = MagicMock()
    mock_client.chat.side_effect = RuntimeError("connection refused")

    with patch("src.summarizer.ollama.Client", return_value=mock_client):
        with pytest.raises(RuntimeError, match="connection refused"):
            summarize("transcript")

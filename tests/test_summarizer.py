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
    """After all retries are exhausted the last exception is re-raised."""
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://localhost:11434")
    monkeypatch.setenv("OLLAMA_MODEL", "mistral")

    mock_client = MagicMock()
    mock_client.chat.side_effect = RuntimeError("connection refused")

    with patch("src.summarizer.ollama.Client", return_value=mock_client):
        with pytest.raises(RuntimeError, match="connection refused"):
            # Use max_retries=1 to avoid sleeps in CI; retry_delay=0 to skip sleep
            summarize("transcript", max_retries=1, retry_delay=0.0)


# ── Retry logic ───────────────────────────────────────────────────────────────


def test_summarize_retries_on_failure(monkeypatch):
    """summarize() retries the configured number of times before giving up."""
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://localhost:11434")
    monkeypatch.setenv("OLLAMA_MODEL", "mistral")

    mock_client = MagicMock()
    mock_client.chat.side_effect = RuntimeError("timeout")

    with patch("src.summarizer.ollama.Client", return_value=mock_client):
        with pytest.raises(RuntimeError):
            summarize("transcript", max_retries=3, retry_delay=0.0)

    assert mock_client.chat.call_count == 3


def test_summarize_succeeds_on_second_attempt(monkeypatch):
    """summarize() returns the result if a later retry succeeds."""
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://localhost:11434")
    monkeypatch.setenv("OLLAMA_MODEL", "mistral")

    ok_response = MagicMock()
    ok_response.message.content = "## Result"

    mock_client = MagicMock()
    mock_client.chat.side_effect = [RuntimeError("first fail"), ok_response]

    with patch("src.summarizer.ollama.Client", return_value=mock_client):
        result = summarize("transcript", max_retries=3, retry_delay=0.0)

    assert result == "## Result"
    assert mock_client.chat.call_count == 2


def test_summarize_respects_max_retries_env_var(monkeypatch):
    """OLLAMA_MAX_RETRIES env var controls the default number of attempts."""
    monkeypatch.setenv("OLLAMA_MAX_RETRIES", "2")
    monkeypatch.setenv("OLLAMA_RETRY_DELAY_S", "0")

    mock_client = MagicMock()
    mock_client.chat.side_effect = RuntimeError("fail")

    with patch("src.summarizer.ollama.Client", return_value=mock_client):
        with pytest.raises(RuntimeError):
            summarize("transcript")

    assert mock_client.chat.call_count == 2


# ── Speaker prompt ────────────────────────────────────────────────────────────


def test_summarize_with_speakers_extends_system_prompt(monkeypatch):
    """When speakers are provided the speaker suffix is appended to the system prompt."""
    from src.summarizer import _SPEAKER_PROMPT_SUFFIX

    monkeypatch.setenv("OLLAMA_BASE_URL", "http://localhost:11434")
    monkeypatch.setenv("OLLAMA_MODEL", "mistral")

    fake_response = MagicMock()
    fake_response.message.content = "## Summary"

    mock_client = MagicMock()
    mock_client.chat.return_value = fake_response

    with patch("src.summarizer.ollama.Client", return_value=mock_client):
        summarize("[Aragorn]: We ride at dawn.", speakers=["Aragorn", "Legolas"])

    call_kwargs = mock_client.chat.call_args[1]
    system_content = call_kwargs["messages"][0]["content"]
    assert _SPEAKER_PROMPT_SUFFIX in system_content


def test_summarize_without_speakers_no_suffix(monkeypatch):
    """Without speakers the system prompt does not include the speaker suffix."""
    from src.summarizer import _SPEAKER_PROMPT_SUFFIX

    monkeypatch.setenv("OLLAMA_BASE_URL", "http://localhost:11434")
    monkeypatch.setenv("OLLAMA_MODEL", "mistral")

    fake_response = MagicMock()
    fake_response.message.content = "## Summary"

    mock_client = MagicMock()
    mock_client.chat.return_value = fake_response

    with patch("src.summarizer.ollama.Client", return_value=mock_client):
        summarize("Generic transcript.")

    call_kwargs = mock_client.chat.call_args[1]
    system_content = call_kwargs["messages"][0]["content"]
    assert _SPEAKER_PROMPT_SUFFIX not in system_content

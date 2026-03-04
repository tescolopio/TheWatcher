"""Tests for src/transcriber.py – backend selection and transcription."""

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.transcriber import _transcribe_with_whisper_cpp, transcribe


# ── whisper.cpp backend ───────────────────────────────────────────────────────


def test_whisper_cpp_returns_stdout(tmp_path, monkeypatch):
    """_transcribe_with_whisper_cpp returns stripped stdout on success."""
    binary = tmp_path / "whisper"
    binary.write_text("")  # just needs to exist for the path check

    monkeypatch.setenv("WHISPER_CPP_PATH", str(binary))
    monkeypatch.setenv("WHISPER_MODEL", "base")

    audio_file = tmp_path / "session.wav"
    audio_file.write_bytes(b"")

    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "  Hello world  \n"
    mock_result.stderr = ""

    with patch("src.transcriber.subprocess.run", return_value=mock_result) as mock_run:
        result = _transcribe_with_whisper_cpp(audio_file)

    assert result == "Hello world"
    call_args = mock_run.call_args[0][0]
    assert str(binary) in call_args
    assert str(audio_file) in call_args


def test_whisper_cpp_raises_on_nonzero_exit(tmp_path, monkeypatch):
    """RuntimeError is raised when whisper.cpp exits with a non-zero code."""
    binary = tmp_path / "whisper"
    binary.write_text("")
    monkeypatch.setenv("WHISPER_CPP_PATH", str(binary))

    mock_result = MagicMock()
    mock_result.returncode = 1
    mock_result.stderr = "model not found"

    with patch("src.transcriber.subprocess.run", return_value=mock_result):
        with pytest.raises(RuntimeError, match="whisper.cpp exited with code 1"):
            _transcribe_with_whisper_cpp(tmp_path / "audio.wav")


# ── openai-whisper Python backend ─────────────────────────────────────────────


def test_python_whisper_calls_model(tmp_path, monkeypatch):
    """_transcribe_with_python_whisper loads the model and returns transcript."""
    monkeypatch.setenv("WHISPER_MODEL", "tiny")

    audio_file = tmp_path / "session.wav"
    audio_file.write_bytes(b"")

    mock_model = MagicMock()
    mock_model.transcribe.return_value = {"text": "  Hello from Whisper  "}

    mock_whisper = MagicMock()
    mock_whisper.load_model.return_value = mock_model

    with patch.dict("sys.modules", {"whisper": mock_whisper}):
        from src.transcriber import _transcribe_with_python_whisper

        result = _transcribe_with_python_whisper(audio_file)

    assert result == "Hello from Whisper"
    mock_whisper.load_model.assert_called_once_with("tiny")
    mock_model.transcribe.assert_called_once_with(str(audio_file))


# ── transcribe() backend selection ───────────────────────────────────────────


def test_transcribe_uses_whisper_cpp_when_configured(tmp_path, monkeypatch):
    """transcribe() selects the whisper.cpp backend when WHISPER_CPP_PATH exists."""
    binary = tmp_path / "whisper"
    binary.touch()
    monkeypatch.setenv("WHISPER_CPP_PATH", str(binary))

    with patch("src.transcriber._transcribe_with_whisper_cpp", return_value="via cpp") as mock_cpp:
        result = transcribe(tmp_path / "audio.wav")

    assert result == "via cpp"
    mock_cpp.assert_called_once()


def test_transcribe_falls_back_to_python_when_no_binary(tmp_path, monkeypatch):
    """transcribe() falls back to the Python backend when WHISPER_CPP_PATH is unset."""
    monkeypatch.delenv("WHISPER_CPP_PATH", raising=False)

    with patch("src.transcriber._transcribe_with_python_whisper", return_value="via py") as mock_py:
        result = transcribe(tmp_path / "audio.wav")

    assert result == "via py"
    mock_py.assert_called_once()


def test_transcribe_falls_back_when_binary_missing(tmp_path, monkeypatch):
    """transcribe() falls back when WHISPER_CPP_PATH points to a nonexistent file."""
    monkeypatch.setenv("WHISPER_CPP_PATH", str(tmp_path / "nonexistent"))

    with patch("src.transcriber._transcribe_with_python_whisper", return_value="fallback") as mock_py:
        result = transcribe(tmp_path / "audio.wav")

    assert result == "fallback"
    mock_py.assert_called_once()

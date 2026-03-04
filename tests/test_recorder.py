"""Tests for src/recorder.py – audio merging and file saving."""

import io
import struct
import wave
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.recorder import _get_recordings_dir, finish_recording, merge_audio_data


# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_raw_pcm(samples: list[int]) -> bytes:
    """Build raw 16-bit signed LE PCM bytes from a list of sample values."""
    return struct.pack(f"<{len(samples)}h", *samples)


def _make_audio_data(samples_per_user: list[list[int]]) -> dict:
    """Return a mock audio_data dict keyed by integer user ID."""
    audio_data = {}
    for uid, samples in enumerate(samples_per_user):
        raw_pcm = _make_raw_pcm(samples)
        mock_audio = MagicMock()
        mock_audio.file = io.BytesIO(raw_pcm)
        audio_data[uid] = mock_audio
    return audio_data


# ── merge_audio_data ──────────────────────────────────────────────────────────


def test_merge_single_track_passthrough():
    """A single user's WAV is returned unchanged (same PCM frames)."""
    samples = [100, -100, 200, -200]
    audio_data = _make_audio_data([samples])
    result = merge_audio_data(audio_data)

    with wave.open(io.BytesIO(result)) as wf:
        frames = wf.readframes(wf.getnframes())

    expected_pcm = struct.pack(f"<{len(samples)}h", *samples)
    assert frames == expected_pcm


def test_merge_two_tracks_sums_samples():
    """Two tracks of equal length are mixed by sample summation."""
    a = [100, 200, 300, 400]
    b = [10, 20, 30, 40]
    audio_data = _make_audio_data([a, b])
    result = merge_audio_data(audio_data)

    with wave.open(io.BytesIO(result)) as wf:
        frames = wf.readframes(wf.getnframes())
    mixed = list(struct.unpack(f"<{len(a)}h", frames))
    assert mixed == [a[i] + b[i] for i in range(len(a))]


def test_merge_pads_shorter_track():
    """The shorter track is zero-padded so that tracks are aligned."""
    long_track = [100, 200, 300, 400]
    short_track = [10, 20]  # shorter – will be padded with zeros
    audio_data = _make_audio_data([long_track, short_track])
    result = merge_audio_data(audio_data)

    with wave.open(io.BytesIO(result)) as wf:
        frames = wf.readframes(wf.getnframes())
    mixed = list(struct.unpack(f"<{len(long_track)}h", frames))
    expected = [110, 220, 300, 400]
    assert mixed == expected


def test_merge_clamps_to_16bit():
    """Overflow is clamped to the 16-bit signed range."""
    a = [30000, -30000]
    b = [30000, -30000]
    audio_data = _make_audio_data([a, b])
    result = merge_audio_data(audio_data)

    with wave.open(io.BytesIO(result)) as wf:
        frames = wf.readframes(wf.getnframes())
    mixed = list(struct.unpack("<2h", frames))
    assert mixed[0] == 32767
    assert mixed[1] == -32768


def test_merge_raises_on_empty_audio():
    """ValueError is raised when no audio data was recorded."""
    mock_audio = MagicMock()
    mock_audio.file = io.BytesIO(b"")  # empty – no WAV header
    with pytest.raises(ValueError, match="No audio data was recorded"):
        merge_audio_data({0: mock_audio})


def test_merge_raises_on_no_users():
    """ValueError is raised when the audio_data dict is empty."""
    with pytest.raises(ValueError, match="No audio data was recorded"):
        merge_audio_data({})


# ── finish_recording ──────────────────────────────────────────────────────────


def test_finish_recording_saves_wav_file(tmp_path, monkeypatch):
    """finish_recording writes a WAV file and returns its path."""
    monkeypatch.setenv("RECORDINGS_DIR", str(tmp_path))

    samples = [100, -100, 200, -200]
    sink = MagicMock()
    sink.audio_data = _make_audio_data([samples])

    result_path = finish_recording(sink)

    assert result_path.exists()
    assert result_path.suffix == ".wav"
    with wave.open(str(result_path)) as wf:
        assert wf.getnframes() > 0


def test_finish_recording_uses_env_dir(tmp_path, monkeypatch):
    """RECORDINGS_DIR env var controls where the file is saved."""
    custom_dir = tmp_path / "recordings"
    monkeypatch.setenv("RECORDINGS_DIR", str(custom_dir))

    sink = MagicMock()
    sink.audio_data = _make_audio_data([[0, 1, 2]])

    result_path = finish_recording(sink)

    assert result_path.parent == custom_dir
    assert custom_dir.exists()


def test_get_recordings_dir_creates_dir(tmp_path, monkeypatch):
    """_get_recordings_dir creates the directory if it does not exist."""
    new_dir = tmp_path / "new_recordings"
    monkeypatch.setenv("RECORDINGS_DIR", str(new_dir))
    assert not new_dir.exists()
    result = _get_recordings_dir()
    assert result == new_dir
    assert new_dir.is_dir()

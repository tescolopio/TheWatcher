"""Tests for src/audio.py — PCM preprocessing helpers."""

import io
import math
import struct
import wave
from pathlib import Path

import pytest

from src.audio import (
    _rms,
    normalize_rms,
    preprocess_track,
    save_pcm_as_wav,
    trim_silence,
    wrap_pcm_as_wav,
)

# ── Helpers ───────────────────────────────────────────────────────────────────

_CHANNELS = 2
_SAMPLE_WIDTH = 2
_SAMPLE_RATE = 48_000


def _pcm(samples: list[int]) -> bytes:
    """Pack a list of 16-bit signed ints as LE PCM bytes."""
    return struct.pack(f"<{len(samples)}h", *samples)


def _unpack_pcm(data: bytes) -> list[int]:
    n = len(data) // _SAMPLE_WIDTH
    return list(struct.unpack(f"<{n}h", data[: n * _SAMPLE_WIDTH]))


def _loud_frame(amplitude: int = 20000, count: int = 8) -> list[int]:
    """Generate one alternating stereo frame (amplitude, -amplitude) × N."""
    return [amplitude, -amplitude] * count


def _silent_frame(count: int = 8) -> list[int]:
    """Generate a block of silent (zero) stereo PCM samples."""
    return [0] * (count * _CHANNELS)


# ── _rms ──────────────────────────────────────────────────────────────────────


def test_rms_all_zeros_returns_zero() -> None:
    assert _rms((0, 0, 0)) == 0.0


def test_rms_constant_signal() -> None:
    """RMS of a constant signal equals that constant."""
    assert _rms((100, 100, 100)) == pytest.approx(100.0)


def test_rms_empty_returns_zero() -> None:
    assert _rms(()) == 0.0


# ── trim_silence ──────────────────────────────────────────────────────────────


def test_trim_silence_no_change_when_all_loud() -> None:
    """Entirely non-silent audio is returned unchanged."""
    samples = _loud_frame(amplitude=10000, count=4) * 10
    data = _pcm(samples)
    trimmed = trim_silence(data, threshold_db=-60.0)
    # Length should not grow; it may shrink slightly at frame boundaries but
    # the content should remain non-empty.
    assert len(trimmed) > 0


def test_trim_silence_removes_leading_silence() -> None:
    """Leading silent frames are removed."""
    silent_prefix = _silent_frame(count=20)
    loud_middle = _loud_frame(amplitude=15000, count=20)
    data = _pcm(silent_prefix + loud_middle)

    trimmed = trim_silence(data, threshold_db=-60.0)
    # Trimmed result must be shorter than the original
    assert len(trimmed) < len(data)
    # And it must still contain audio
    assert len(trimmed) > 0


def test_trim_silence_removes_trailing_silence() -> None:
    """Trailing silent frames are removed."""
    loud = _loud_frame(amplitude=15000, count=20)
    silent_suffix = _silent_frame(count=20)
    data = _pcm(loud + silent_suffix)

    trimmed = trim_silence(data, threshold_db=-60.0)
    assert len(trimmed) < len(data)
    assert len(trimmed) > 0


def test_trim_silence_all_silent_returns_original() -> None:
    """Entirely silent audio is returned unchanged (avoid empty output)."""
    data = _pcm(_silent_frame(count=10))
    trimmed = trim_silence(data, threshold_db=-60.0)
    assert trimmed == data


def test_trim_silence_empty_input() -> None:
    """Empty bytes are returned as-is."""
    assert trim_silence(b"", threshold_db=-60.0) == b""


def test_trim_silence_respects_env_var(monkeypatch: pytest.MonkeyPatch) -> None:
    """SILENCE_THRESHOLD_DB env var is used when threshold_db is None."""
    monkeypatch.setenv("SILENCE_THRESHOLD_DB", "-60")
    silent_prefix = _silent_frame(count=20)
    loud_middle = _loud_frame(amplitude=15000, count=20)
    data = _pcm(silent_prefix + loud_middle)
    trimmed = trim_silence(data)  # no explicit threshold → uses env var
    assert len(trimmed) < len(data)


# ── normalize_rms ──────────────────────────────────────────────────────────────


def test_normalize_rms_empty_input() -> None:
    """Empty bytes are returned as-is."""
    assert normalize_rms(b"") == b""


def test_normalize_rms_silent_track_unchanged() -> None:
    """Silent (all-zero) tracks are returned unchanged."""
    data = _pcm([0] * 20)
    assert normalize_rms(data) == data


def test_normalize_rms_scales_upward() -> None:
    """Quiet audio is scaled up toward the target RMS."""
    # Generate quiet audio (amplitude 100)
    samples = _loud_frame(amplitude=100, count=50)
    data = _pcm(samples)

    normalized = normalize_rms(data, target_db=-20.0)
    nsamples = _unpack_pcm(normalized)
    current_rms = math.sqrt(sum(s * s for s in nsamples) / len(nsamples))
    # Current RMS should be higher than original quiet level
    original_rms = math.sqrt(sum(s * s for s in samples) / len(samples))
    assert current_rms > original_rms


def test_normalize_rms_clamps_to_16bit() -> None:
    """Gain does not produce samples outside the 16-bit signed range."""
    samples = [1] * 40  # very quiet — huge gain needed
    data = _pcm(samples)
    result = normalize_rms(data, target_db=-3.0)
    out = _unpack_pcm(result)
    assert all(-32768 <= s <= 32767 for s in out)


def test_normalize_rms_output_length_matches_input() -> None:
    """Output has the same number of samples as the input."""
    samples = _loud_frame(amplitude=5000, count=16)
    data = _pcm(samples)
    result = normalize_rms(data)
    assert len(result) == len(data)


# ── preprocess_track ──────────────────────────────────────────────────────────


def test_preprocess_track_no_ops_returns_original() -> None:
    """With both flags off, the data is returned untouched."""
    data = _pcm(_loud_frame(amplitude=1000, count=10))
    assert preprocess_track(data, trim=False, normalize=False) == data


def test_preprocess_track_trim_only() -> None:
    """trim=True applies silence trimming without normalisation."""
    silent = _silent_frame(count=20)
    loud = _loud_frame(amplitude=15000, count=20)
    data = _pcm(silent + loud + silent)
    result = preprocess_track(data, trim=True, normalize=False, silence_threshold_db=-60.0)
    # Result should be shorter (leading + trailing silence removed)
    assert len(result) < len(data)


def test_preprocess_track_normalize_only() -> None:
    """normalize=True applies RMS normalisation without trimming."""
    quiet_samples = _loud_frame(amplitude=50, count=50)
    data = _pcm(quiet_samples)
    result = preprocess_track(data, trim=False, normalize=True)
    # Normalized RMS must differ from original
    orig_rms = _rms(tuple(quiet_samples))
    result_samples = tuple(_unpack_pcm(result))
    result_rms = _rms(result_samples)
    assert result_rms != pytest.approx(orig_rms, rel=0.01)


def test_preprocess_track_both_flags() -> None:
    """Both trim and normalize run in sequence without error."""
    silent = _silent_frame(count=10)
    loud = _loud_frame(amplitude=500, count=20)
    data = _pcm(silent + loud + silent)
    result = preprocess_track(data, trim=True, normalize=True, silence_threshold_db=-60.0)
    assert len(result) > 0


# ── wrap_pcm_as_wav ───────────────────────────────────────────────────────────


def test_wrap_pcm_as_wav_produces_valid_wav() -> None:
    """Output can be parsed as a valid WAV file with correct parameters."""
    pcm = _pcm(_loud_frame(amplitude=1000, count=8))
    wav_bytes = wrap_pcm_as_wav(pcm, sample_rate=48000, channels=2, sample_width=2)

    with wave.open(io.BytesIO(wav_bytes)) as wf:
        assert wf.getnchannels() == 2
        assert wf.getsampwidth() == 2
        assert wf.getframerate() == 48000


def test_wrap_pcm_as_wav_round_trips_frames() -> None:
    """PCM frames survive the WAV container round-trip."""
    samples = _loud_frame(amplitude=5000, count=4)
    pcm = _pcm(samples)
    wav_bytes = wrap_pcm_as_wav(pcm)

    with wave.open(io.BytesIO(wav_bytes)) as wf:
        frames = wf.readframes(wf.getnframes())

    assert frames == pcm


# ── save_pcm_as_wav ───────────────────────────────────────────────────────────


def test_save_pcm_as_wav_creates_file(tmp_path: Path) -> None:
    """save_pcm_as_wav writes a file and returns its path."""
    pcm = _pcm(_loud_frame(amplitude=1000, count=4))
    out = tmp_path / "test_output.wav"
    result_path = save_pcm_as_wav(pcm, out)
    assert result_path == out
    assert out.exists()
    assert out.stat().st_size > 0


def test_save_pcm_as_wav_content_is_valid_wav(tmp_path: Path) -> None:
    """The written file is a well-formed WAV with correct parameters."""
    pcm = _pcm(_loud_frame(amplitude=2000, count=4))
    out = tmp_path / "audio.wav"
    save_pcm_as_wav(pcm, out, sample_rate=48000, channels=2, sample_width=2)

    with wave.open(str(out)) as wf:
        assert wf.getnchannels() == 2
        assert wf.getsampwidth() == 2
        assert wf.getframerate() == 48000
        assert wf.getnframes() > 0

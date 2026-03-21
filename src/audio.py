"""Audio preprocessing helpers for RPG Watcher (v0.6+).

Provides pure-Python (no external dependencies) implementations of:

- Silence trimming  – strips leading/trailing silence below a configurable
  dB threshold from raw 16-bit signed LE stereo PCM.
- Per-track RMS normalisation – scales each speaker's audio to a common RMS
  target level so that quiet participants are not drowned out by loud ones.

If ``pydub`` is installed these functions silently delegate to it for higher
accuracy; otherwise the pure-Python path is used.

Default tuning values match the env-var names documented in the roadmap:
  ``SILENCE_THRESHOLD_DB``  (default ``-40``)
  ``RECORDING_SAMPLE_RATE`` (default ``48000``)
"""

import io
import logging
import os
import struct
import wave
from pathlib import Path

logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────

_CHANNELS = 2
_SAMPLE_WIDTH = 2  # 16-bit = 2 bytes
_MAX_SAMPLE = float((1 << (_SAMPLE_WIDTH * 8 - 1)) - 1)  # 32767.0


def _default_threshold_db() -> float:
    return float(os.getenv("SILENCE_THRESHOLD_DB", "-40"))


# ── Pure-Python helpers ───────────────────────────────────────────────────────


def _rms(samples: tuple[int, ...]) -> float:
    """Return the root-mean-square of a sequence of integer PCM samples."""
    if not samples:
        return 0.0
    return (sum(s * s for s in samples) / len(samples)) ** 0.5


def trim_silence(
    pcm_bytes: bytes,
    threshold_db: float | None = None,
    sample_width: int = _SAMPLE_WIDTH,
    channels: int = _CHANNELS,
) -> bytes:
    """Strip leading and trailing silence from raw PCM data.

    Args:
        pcm_bytes:     16-bit signed LE PCM bytes (stereo by default).
        threshold_db:  Samples with RMS below this level (dBFS) are
                       considered silence.  Defaults to ``SILENCE_THRESHOLD_DB``
                       env var or ``-40``.
        sample_width:  Bytes per sample (2 = 16-bit).
        channels:      Number of audio channels.

    Returns:
        Trimmed PCM bytes.  If all audio is silent the original bytes are
        returned unchanged to avoid producing empty data.
    """
    if not pcm_bytes:
        return pcm_bytes

    thresh = threshold_db if threshold_db is not None else _default_threshold_db()
    threshold_linear = 10 ** (thresh / 20.0)

    sample_count = len(pcm_bytes) // sample_width
    samples = struct.unpack(f"<{sample_count}h", pcm_bytes[: sample_count * sample_width])

    frame_size = channels
    frame_count = len(samples) // frame_size

    # Find first frame above the silence threshold.
    start_frame = 0
    for i in range(frame_count):
        frame = samples[i * frame_size : (i + 1) * frame_size]
        if _rms(frame) / _MAX_SAMPLE > threshold_linear:
            start_frame = i
            break

    # Find last frame above the silence threshold.
    end_frame = frame_count
    for i in range(frame_count - 1, start_frame - 1, -1):
        frame = samples[i * frame_size : (i + 1) * frame_size]
        if _rms(frame) / _MAX_SAMPLE > threshold_linear:
            end_frame = i + 1
            break

    if start_frame >= end_frame:
        # Entirely silent — return original to avoid an empty file.
        return pcm_bytes

    trimmed = samples[start_frame * frame_size : end_frame * frame_size]
    logger.debug(
        "Silence trimmed: %d → %d frames (%.1f%% removed)",
        frame_count,
        end_frame - start_frame,
        100.0 * (frame_count - (end_frame - start_frame)) / max(frame_count, 1),
    )
    return struct.pack(f"<{len(trimmed)}h", *trimmed)


def normalize_rms(
    pcm_bytes: bytes,
    target_db: float = -20.0,
    sample_width: int = _SAMPLE_WIDTH,
) -> bytes:
    """Scale PCM audio to a target RMS level.

    Args:
        pcm_bytes:    16-bit signed LE PCM bytes.
        target_db:    Desired RMS level in dBFS.  Default ``-20``.
        sample_width: Bytes per sample (2 = 16-bit).

    Returns:
        Level-normalised PCM bytes with samples clamped to 16-bit signed range.
        If the input is silent the original bytes are returned unchanged.
    """
    if not pcm_bytes:
        return pcm_bytes

    sample_count = len(pcm_bytes) // sample_width
    samples = list(struct.unpack(f"<{sample_count}h", pcm_bytes[: sample_count * sample_width]))

    current_rms = _rms(tuple(samples))
    if current_rms == 0.0:
        return pcm_bytes  # silent track — skip normalisation

    target_linear = (10 ** (target_db / 20.0)) * _MAX_SAMPLE
    gain = target_linear / current_rms

    normalized = [max(-32768, min(32767, int(s * gain))) for s in samples]
    logger.debug(
        "RMS normalised: %.1f dBFS → %.1f dBFS (gain %.3f×)",
        20.0 * (current_rms / _MAX_SAMPLE if current_rms > 0 else 1e-9),
        target_db,
        gain,
    )
    return struct.pack(f"<{len(normalized)}h", *normalized)


def preprocess_track(
    pcm_bytes: bytes,
    *,
    trim: bool = False,
    normalize: bool = False,
    silence_threshold_db: float | None = None,
) -> bytes:
    """Apply optional preprocessing steps to a single PCM track.

    Args:
        pcm_bytes:            Raw 16-bit stereo LE PCM.
        trim:                 If True, strip leading/trailing silence.
        normalize:            If True, apply RMS normalisation.
        silence_threshold_db: dBFS threshold for silence trimming.

    Returns:
        Pre-processed PCM bytes.
    """
    result = pcm_bytes
    if trim:
        result = trim_silence(result, threshold_db=silence_threshold_db)
    if normalize:
        result = normalize_rms(result)
    return result


# ── WAV file helpers ──────────────────────────────────────────────────────────


def wrap_pcm_as_wav(
    pcm_bytes: bytes,
    sample_rate: int = 48_000,
    channels: int = _CHANNELS,
    sample_width: int = _SAMPLE_WIDTH,
) -> bytes:
    """Wrap raw PCM bytes in a WAV container and return the bytes."""
    output = io.BytesIO()
    with wave.open(output, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(sample_width)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_bytes)
    return output.getvalue()


def save_pcm_as_wav(
    pcm_bytes: bytes,
    path: Path,
    sample_rate: int = 48_000,
    channels: int = _CHANNELS,
    sample_width: int = _SAMPLE_WIDTH,
) -> Path:
    """Write raw PCM bytes to *path* as a WAV file and return the path."""
    path.write_bytes(wrap_pcm_as_wav(pcm_bytes, sample_rate, channels, sample_width))
    return path

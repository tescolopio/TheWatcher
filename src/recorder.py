"""Audio recording via Discord voice recording sinks (py-cord PCMSink).

Records per-user raw PCM audio from a Discord voice channel using PCMSink,
then merges all user tracks into a single stereo WAV file saved to disk.

Discord sends 48 kHz, 16-bit, stereo PCM; those constants are used to write
the final WAV container.

v0.6 additions:
  ``finish_recording`` accepts optional *trim_silence* and *normalize* flags
  that delegate to :mod:`src.audio` pre-processing helpers.

  ``extract_per_speaker_audio`` saves each speaker's audio to a separate WAV
  file (used for speaker-attributed transcription in v0.5+).
"""

import io
import os
import struct
import wave
from datetime import datetime
from pathlib import Path
from typing import Any

from discord.sinks import PCMSink

from src.audio import preprocess_track, wrap_pcm_as_wav

# Discord Opus decoder constants (16-bit stereo @ 48 kHz)
_SAMPLE_RATE = 48_000
_CHANNELS = 2
_SAMPLE_WIDTH = 2  # bytes per channel sample (16-bit)


def _get_recordings_dir() -> Path:
    """Return (and create if needed) the local directory for saved recordings."""
    recordings_dir = Path(os.getenv("RECORDINGS_DIR", "/tmp/thewatcher_recordings"))
    recordings_dir.mkdir(parents=True, exist_ok=True)
    return recordings_dir


class RecordingSink(PCMSink):
    """PCMSink subclass used as the recording sink for TheWatcher sessions."""


def merge_audio_data(
    audio_data: dict[Any, Any],
    trim_silence: bool = False,
    normalize: bool = False,
) -> bytes:
    """Mix per-user raw PCM audio into a single stereo WAV file.

    Each value in *audio_data* has a ``file`` attribute (``BytesIO``) containing
    interleaved 16-bit signed LE PCM samples at 48 kHz, 2 channels.

    Shorter tracks are zero-padded to match the longest track before mixing.
    Mixed samples are clamped to the 16-bit signed range (−32768 … 32767).

    Args:
        audio_data:    Mapping of user_id -> AudioData as produced by PCMSink.
        trim_silence:  Apply silence trimming to each track before mixing.
        normalize:     Apply RMS normalisation to each track before mixing.

    Returns:
        Raw bytes of a merged stereo WAV file.

    Raises:
        ValueError: If no audio data was recorded.
    """
    pcm_tracks: list[bytes] = []

    for audio in audio_data.values():
        audio.file.seek(0)
        raw = audio.file.read()
        if raw:
            processed = preprocess_track(raw, trim=trim_silence, normalize=normalize)
            pcm_tracks.append(processed)

    if not pcm_tracks:
        raise ValueError("No audio data was recorded.")

    if len(pcm_tracks) == 1:
        mixed_pcm = pcm_tracks[0]
    else:
        # Align all tracks to the same length by zero-padding shorter ones.
        max_len = max(len(t) for t in pcm_tracks)
        padded = [t + b"\x00" * (max_len - len(t)) for t in pcm_tracks]

        # Mix by summing 16-bit signed samples and clamping.
        sample_count = max_len // _SAMPLE_WIDTH
        fmt = f"<{sample_count}h"
        samples_list = [struct.unpack(fmt, p) for p in padded]
        mixed = [
            max(-32768, min(32767, sum(s[i] for s in samples_list)))
            for i in range(sample_count)
        ]
        mixed_pcm = struct.pack(fmt, *mixed)

    # Wrap the mixed PCM in a WAV container.
    output = io.BytesIO()
    with wave.open(output, "wb") as wf:
        wf.setnchannels(_CHANNELS)
        wf.setsampwidth(_SAMPLE_WIDTH)
        wf.setframerate(_SAMPLE_RATE)
        wf.writeframes(mixed_pcm)
    return output.getvalue()


def finish_recording(
    sink: RecordingSink,
    trim_silence: bool = False,
    normalize: bool = False,
) -> Path:
    """Save the merged recording to a WAV file on disk and return its path.

    Per-user tracks are optionally pre-processed (silence-trimmed and/or
    RMS-normalised) before mixing.

    Args:
        sink:          A RecordingSink that has already been stopped.
        trim_silence:  If True, strip leading/trailing silence from each track
                       before mixing.  Controlled by ``SILENCE_THRESHOLD_DB``.
        normalize:     If True, RMS-normalise each track before mixing so that
                       quiet speakers are not drowned out by loud ones.

    Returns:
        Path to the saved WAV file.
    """
    recordings_dir = _get_recordings_dir()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = recordings_dir / f"session_{timestamp}.wav"

    wav_bytes = merge_audio_data(
        sink.audio_data,
        trim_silence=trim_silence,
        normalize=normalize,
    )
    output_path.write_bytes(wav_bytes)

    return output_path


def extract_per_speaker_audio(
    sink: RecordingSink,
    output_dir: Path,
    trim_silence: bool = False,
    normalize: bool = False,
) -> dict[str, Path]:
    """Save each speaker's audio as an individual WAV file.

    Returns a mapping of ``str(user_id) -> Path`` for non-empty tracks only.
    Used for speaker-attributed transcription (v0.5+).

    Args:
        sink:          A stopped RecordingSink.
        output_dir:    Directory in which to save per-speaker WAV files.
        trim_silence:  Apply silence trimming to each track.
        normalize:     Apply RMS normalisation to each track.

    Returns:
        ``{str(user_id): wav_path}`` for tracks with audio data.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    paths: dict[str, Path] = {}
    for user_id, audio_obj in sink.audio_data.items():
        audio_obj.file.seek(0)
        raw = audio_obj.file.read()
        if not raw:
            continue
        processed = preprocess_track(raw, trim=trim_silence, normalize=normalize)
        wav_path = output_dir / f"speaker_{user_id}.wav"
        wav_path.write_bytes(wrap_pcm_as_wav(processed))
        paths[str(user_id)] = wav_path
    return paths

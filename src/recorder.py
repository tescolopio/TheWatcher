"""Audio recording via Discord voice recording sinks (py-cord PCMSink).

Records per-user raw PCM audio from a Discord voice channel using PCMSink,
then merges all user tracks into a single stereo WAV file saved to disk.

Discord sends 48 kHz, 16-bit, stereo PCM; those constants are used to write
the final WAV container.
"""

import io
import os
import struct
import wave
from datetime import datetime
from pathlib import Path

from discord.sinks import PCMSink

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


def merge_audio_data(audio_data: dict) -> bytes:
    """Mix per-user raw PCM audio into a single stereo WAV file.

    Each value in *audio_data* has a ``file`` attribute (``BytesIO``) containing
    interleaved 16-bit signed LE PCM samples at 48 kHz, 2 channels.

    Shorter tracks are zero-padded to match the longest track before mixing.
    Mixed samples are clamped to the 16-bit signed range (−32768 … 32767).

    Args:
        audio_data: Mapping of user_id -> AudioData as produced by PCMSink.

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
            pcm_tracks.append(raw)

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


def finish_recording(sink: RecordingSink) -> Path:
    """Save the merged recording to a WAV file on disk and return its path.

    Args:
        sink: A RecordingSink that has already been stopped by the VoiceClient.

    Returns:
        Path to the saved WAV file.
    """
    recordings_dir = _get_recordings_dir()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = recordings_dir / f"session_{timestamp}.wav"

    wav_bytes = merge_audio_data(sink.audio_data)
    output_path.write_bytes(wav_bytes)

    return output_path

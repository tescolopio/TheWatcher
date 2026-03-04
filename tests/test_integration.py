"""Integration smoke test — mocks external services and runs the full pipeline.

This test exercises the complete record → transcribe → summarise → save-to-Obsidian
path using *real* recorder and obsidian code, mocking only the Whisper and Ollama
calls that require external binaries or network access.
"""

import io
import struct
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.bot import _on_recording_finished


def _make_sink(samples: list[int]) -> MagicMock:
    """Build a mock RecordingSink with a single audio track of the given samples."""
    raw_pcm = struct.pack(f"<{len(samples)}h", *samples)
    mock_audio = MagicMock()
    mock_audio.file = io.BytesIO(raw_pcm)

    sink = MagicMock()
    sink.audio_data = {0: mock_audio}
    return sink


@pytest.mark.asyncio
async def test_full_pipeline_end_to_end(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Smoke test: from a RecordingSink all the way to a written Obsidian note.

    External services (Whisper, Ollama) are mocked.  The recorder (WAV merge + write)
    and Obsidian writer (front-matter + file creation) run with real code.
    """
    monkeypatch.setenv("RECORDINGS_DIR", str(tmp_path))
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(tmp_path))
    monkeypatch.setenv("OBSIDIAN_NOTES_FOLDER", "SessionNotes")

    # Use a 0.1-second clip of silence so the WAV is valid but fast.
    silence = [0] * (48_000 * 2 // 10)  # 48 kHz stereo × 0.1 s
    sink = _make_sink(silence)

    channel: AsyncMock = AsyncMock()
    vc: AsyncMock = AsyncMock()

    fake_summary = (
        "## Session Overview\n"
        "The adventurers cleared a goblin dungeon.\n\n"
        "## Key Events\n"
        "1. Entered the dungeon.\n"
        "2. Defeated the goblin chieftain.\n\n"
        "## NPC Interactions\n"
        "- Goblin Chieftain: defeated in combat.\n\n"
        "## Player Decisions\n"
        "- Chose to spare the goblin shaman.\n\n"
        "## Cliffhangers / Open Threads\n"
        "- The shaman escaped with a mysterious amulet.\n"
    )

    with (
        patch("src.bot.transcribe", return_value="The adventurers cleared a goblin dungeon."),
        patch("src.bot.summarize", return_value=fake_summary),
    ):
        await _on_recording_finished(sink, channel, vc)

    # ── Assertions ─────────────────────────────────────────────────────────────

    # The voice client must have been disconnected.
    vc.disconnect.assert_awaited_once()

    # A WAV recording was saved to disk.
    wav_files = list(tmp_path.glob("*.wav"))
    assert len(wav_files) == 1, f"Expected 1 WAV file, found: {wav_files}"

    # An Obsidian note was written.
    notes_dir = tmp_path / "SessionNotes"
    md_files = list(notes_dir.glob("*.md"))
    assert len(md_files) == 1, f"Expected 1 Markdown note, found: {md_files}"

    note_content = md_files[0].read_text(encoding="utf-8")
    # YAML front-matter present.
    assert note_content.startswith("---\n"), "Note must begin with YAML front-matter"
    assert "session-notes" in note_content
    assert "ttrpg" in note_content
    # Summary content preserved.
    assert "Session Overview" in note_content
    assert "goblin" in note_content.lower()

    # Discord received the expected status sequence.
    sent_messages = [str(c) for c in channel.send.call_args_list]
    assert any("Saving" in m or "🔄" in m for m in sent_messages), "Expected save status"
    assert any("Transcrib" in m or "🗣" in m for m in sent_messages), "Expected transcribe status"
    assert any("summar" in m.lower() or "🧠" in m for m in sent_messages), "Expected summary status"
    assert any("✅" in m for m in sent_messages), "Expected completion message"


@pytest.mark.asyncio
async def test_pipeline_produces_valid_wav(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The WAV file written by the recorder is a valid, readable WAV."""
    import wave

    monkeypatch.setenv("RECORDINGS_DIR", str(tmp_path))
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(tmp_path))

    samples = [i % 32767 for i in range(9600)]  # 0.1 s @ 48 kHz stereo
    sink = _make_sink(samples)

    channel: AsyncMock = AsyncMock()
    vc: AsyncMock = AsyncMock()

    with (
        patch("src.bot.transcribe", return_value="test transcript"),
        patch("src.bot.summarize", return_value="## Overview\nTest session."),
    ):
        await _on_recording_finished(sink, channel, vc)

    wav_files = list(tmp_path.glob("*.wav"))
    assert len(wav_files) == 1

    with wave.open(str(wav_files[0])) as wf:
        assert wf.getnchannels() == 2
        assert wf.getsampwidth() == 2
        assert wf.getframerate() == 48_000
        assert wf.getnframes() > 0


@pytest.mark.asyncio
async def test_pipeline_two_speakers_merged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Two-speaker audio is correctly merged into a single WAV before transcription."""
    monkeypatch.setenv("RECORDINGS_DIR", str(tmp_path))
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(tmp_path))

    # Two speakers with distinct PCM content.
    speaker_a = [100] * 200
    speaker_b = [200] * 200

    raw_a = struct.pack(f"<{len(speaker_a)}h", *speaker_a)
    raw_b = struct.pack(f"<{len(speaker_b)}h", *speaker_b)

    audio_a, audio_b = MagicMock(), MagicMock()
    audio_a.file = io.BytesIO(raw_a)
    audio_b.file = io.BytesIO(raw_b)

    sink = MagicMock()
    sink.audio_data = {0: audio_a, 1: audio_b}

    channel: AsyncMock = AsyncMock()
    vc: AsyncMock = AsyncMock()

    recorded_path: list[Path] = []

    def capture_transcribe(path: Path) -> str:
        recorded_path.append(path)
        return "Two speakers."

    with (
        patch("src.bot.transcribe", side_effect=capture_transcribe),
        patch("src.bot.summarize", return_value="## Overview\nTwo speakers session."),
    ):
        await _on_recording_finished(sink, channel, vc)

    assert len(recorded_path) == 1, "transcribe() must be called exactly once"
    assert recorded_path[0].suffix == ".wav"
    vc.disconnect.assert_awaited_once()

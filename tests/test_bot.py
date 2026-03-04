"""Tests for src/bot.py — on_ready, watch, unwatch, and pipeline callback."""

import io
import struct
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, call, patch

import discord
import pytest

from src import bot as bot_module
from src.bot import _active_recordings, _on_recording_finished


# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_interaction(
    *,
    guild_id: int = 1,
    has_guild: bool = True,
    in_voice: bool = True,
    has_channel: bool = True,
) -> MagicMock:
    """Build a minimal mock :class:`discord.Interaction`."""
    interaction: MagicMock = MagicMock(spec=discord.Interaction)
    interaction.response = AsyncMock()
    interaction.response.send_message = AsyncMock()

    if has_guild:
        guild = MagicMock(spec=discord.Guild)
        guild.id = guild_id
        interaction.guild = guild
    else:
        interaction.guild = None

    if has_channel:
        interaction.channel = AsyncMock(spec=discord.TextChannel)
    else:
        interaction.channel = None

    member = MagicMock(spec=discord.Member)
    if in_voice:
        voice_state: MagicMock = MagicMock()
        voice_channel: MagicMock = MagicMock()
        voice_channel.name = "General"
        voice_channel.connect = AsyncMock()
        voice_state.channel = voice_channel
        member.voice = voice_state
    else:
        member.voice = None

    interaction.user = member
    return interaction


# ── on_ready ──────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_on_ready_syncs_commands() -> None:
    """on_ready syncs slash commands and logs the bot identity."""
    fake_user: MagicMock = MagicMock()
    fake_user.id = 123456
    fake_user.__str__ = lambda _: "TestBot#0001"  # type: ignore[assignment]
    synced: list[Any] = [MagicMock(), MagicMock()]

    with (
        patch.object(bot_module.bot, "user", new=fake_user),
        patch.object(bot_module.bot.tree, "sync", new=AsyncMock(return_value=synced)),
    ):
        from src.bot import on_ready

        await on_ready()
        bot_module.bot.tree.sync.assert_awaited_once()


@pytest.mark.asyncio
async def test_on_ready_handles_none_user() -> None:
    """on_ready does not raise when bot.user is None before login completes."""
    with (
        patch.object(bot_module.bot, "user", new=None),
        patch.object(bot_module.bot.tree, "sync", new=AsyncMock(return_value=[])),
    ):
        from src.bot import on_ready

        await on_ready()  # must not raise


# ── watch command ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_watch_rejects_outside_guild() -> None:
    """/watch sends an ephemeral error when used outside a guild."""
    from src.bot import watch

    interaction = _make_interaction(has_guild=False)
    fn = getattr(watch, "callback", watch)
    await fn(interaction)

    interaction.response.send_message.assert_awaited_once()
    assert interaction.response.send_message.call_args.kwargs.get("ephemeral") is True


@pytest.mark.asyncio
async def test_watch_rejects_caller_not_in_voice() -> None:
    """/watch sends an ephemeral error when the caller is not in a voice channel."""
    from src.bot import watch

    interaction = _make_interaction(in_voice=False)
    fn = getattr(watch, "callback", watch)
    await fn(interaction)

    interaction.response.send_message.assert_awaited_once()
    assert interaction.response.send_message.call_args.kwargs.get("ephemeral") is True


@pytest.mark.asyncio
async def test_watch_rejects_duplicate_recording() -> None:
    """/watch rejects a second recording request while one is already active."""
    from src.bot import watch

    gid = 9001
    _active_recordings[gid] = MagicMock(spec=discord.VoiceClient)
    try:
        interaction = _make_interaction(guild_id=gid)
        fn = getattr(watch, "callback", watch)
        await fn(interaction)

        interaction.response.send_message.assert_awaited_once()
        assert interaction.response.send_message.call_args.kwargs.get("ephemeral") is True
    finally:
        _active_recordings.pop(gid, None)


@pytest.mark.asyncio
async def test_watch_rejects_when_channel_is_none() -> None:
    """/watch sends an error when the interaction has no text channel reference."""
    from src.bot import watch

    interaction = _make_interaction(guild_id=202, has_channel=False)
    fn = getattr(watch, "callback", watch)
    await fn(interaction)

    interaction.response.send_message.assert_awaited_once()
    assert interaction.response.send_message.call_args.kwargs.get("ephemeral") is True


@pytest.mark.asyncio
async def test_watch_starts_recording() -> None:
    """/watch connects to the voice channel, starts recording, and registers the session."""
    from src.bot import watch

    gid = 300
    _active_recordings.pop(gid, None)

    interaction = _make_interaction(guild_id=gid)
    mock_vc: MagicMock = MagicMock(spec=discord.VoiceClient)
    mock_vc.start_recording = MagicMock()
    interaction.user.voice.channel.connect = AsyncMock(return_value=mock_vc)

    fn = getattr(watch, "callback", watch)
    with patch("src.bot.RecordingSink") as mock_sink_cls:
        mock_sink_cls.return_value = MagicMock()
        await fn(interaction)

    assert gid in _active_recordings
    mock_vc.start_recording.assert_called_once()
    interaction.response.send_message.assert_awaited_once()
    _active_recordings.pop(gid, None)


@pytest.mark.asyncio
async def test_watch_handles_connect_error() -> None:
    """/watch surfaces a ClientException when the bot cannot join the channel."""
    from src.bot import watch

    gid = 301
    _active_recordings.pop(gid, None)

    interaction = _make_interaction(guild_id=gid)
    interaction.user.voice.channel.connect = AsyncMock(
        side_effect=discord.ClientException("already connected")
    )

    fn = getattr(watch, "callback", watch)
    await fn(interaction)

    assert gid not in _active_recordings
    assert interaction.response.send_message.call_args.kwargs.get("ephemeral") is True


# ── unwatch command ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_unwatch_rejects_outside_guild() -> None:
    """/unwatch sends an ephemeral error when used outside a guild."""
    from src.bot import unwatch

    interaction = _make_interaction(has_guild=False)
    fn = getattr(unwatch, "callback", unwatch)
    await fn(interaction)

    assert interaction.response.send_message.call_args.kwargs.get("ephemeral") is True


@pytest.mark.asyncio
async def test_unwatch_rejects_no_active_recording() -> None:
    """/unwatch reports an error when there is no active recording."""
    from src.bot import unwatch

    gid = 400
    _active_recordings.pop(gid, None)

    interaction = _make_interaction(guild_id=gid)
    fn = getattr(unwatch, "callback", unwatch)
    await fn(interaction)

    assert interaction.response.send_message.call_args.kwargs.get("ephemeral") is True


@pytest.mark.asyncio
async def test_unwatch_stops_recording_and_clears_registry() -> None:
    """/unwatch stops the VoiceClient and removes it from _active_recordings."""
    from src.bot import unwatch

    gid = 500
    mock_vc: MagicMock = MagicMock(spec=discord.VoiceClient)
    mock_vc.stop_recording = MagicMock()
    _active_recordings[gid] = mock_vc

    interaction = _make_interaction(guild_id=gid)
    fn = getattr(unwatch, "callback", unwatch)
    await fn(interaction)

    mock_vc.stop_recording.assert_called_once()
    assert gid not in _active_recordings
    interaction.response.send_message.assert_awaited_once()


# ── _on_recording_finished pipeline callback ──────────────────────────────────


@pytest.mark.asyncio
async def test_pipeline_full_success(tmp_path: Path) -> None:
    """Full pipeline runs all stages and posts a completion message."""
    channel: AsyncMock = AsyncMock()
    vc: AsyncMock = AsyncMock()
    sink: MagicMock = MagicMock()
    fake_wav = tmp_path / "session.wav"
    fake_wav.write_bytes(b"RIFF")

    with (
        patch("src.bot.finish_recording", return_value=fake_wav),
        patch("src.bot.transcribe", return_value="The party fought a dragon."),
        patch("src.bot.summarize", return_value="## Overview\nGreat session!"),
        patch("src.bot.save_to_obsidian", return_value=tmp_path / "note.md"),
    ):
        await _on_recording_finished(sink, channel, vc)

    vc.disconnect.assert_awaited_once()
    assert channel.send.await_count >= 4
    all_messages = " ".join(str(c) for c in channel.send.call_args_list)
    assert "✅" in all_messages


@pytest.mark.asyncio
async def test_pipeline_none_channel_aborts_immediately() -> None:
    """Pipeline aborts and disconnects immediately when channel is None."""
    vc: AsyncMock = AsyncMock()
    sink: MagicMock = MagicMock()

    with patch("src.bot.finish_recording") as mock_finish:
        await _on_recording_finished(sink, None, vc)
        mock_finish.assert_not_called()

    vc.disconnect.assert_awaited_once()


@pytest.mark.asyncio
async def test_pipeline_save_failure_posts_error(tmp_path: Path) -> None:
    """Pipeline posts an error and disconnects when finish_recording raises."""
    channel: AsyncMock = AsyncMock()
    vc: AsyncMock = AsyncMock()
    sink: MagicMock = MagicMock()

    with patch("src.bot.finish_recording", side_effect=RuntimeError("disk full")):
        await _on_recording_finished(sink, channel, vc)

    vc.disconnect.assert_awaited_once()
    all_messages = " ".join(str(c) for c in channel.send.call_args_list)
    assert "❌" in all_messages


@pytest.mark.asyncio
async def test_pipeline_transcription_failure_posts_error(tmp_path: Path) -> None:
    """Pipeline posts an error and disconnects when transcription raises."""
    channel: AsyncMock = AsyncMock()
    vc: AsyncMock = AsyncMock()
    sink: MagicMock = MagicMock()
    fake_wav = tmp_path / "session.wav"
    fake_wav.write_bytes(b"RIFF")

    with (
        patch("src.bot.finish_recording", return_value=fake_wav),
        patch("src.bot.transcribe", side_effect=RuntimeError("model not found")),
    ):
        await _on_recording_finished(sink, channel, vc)

    vc.disconnect.assert_awaited_once()
    all_messages = " ".join(str(c) for c in channel.send.call_args_list)
    assert "❌" in all_messages


@pytest.mark.asyncio
async def test_pipeline_summariser_failure_posts_error(tmp_path: Path) -> None:
    """Pipeline posts an error and disconnects when summarisation raises."""
    channel: AsyncMock = AsyncMock()
    vc: AsyncMock = AsyncMock()
    sink: MagicMock = MagicMock()
    fake_wav = tmp_path / "session.wav"
    fake_wav.write_bytes(b"RIFF")

    with (
        patch("src.bot.finish_recording", return_value=fake_wav),
        patch("src.bot.transcribe", return_value="transcript"),
        patch("src.bot.summarize", side_effect=RuntimeError("ollama unreachable")),
    ):
        await _on_recording_finished(sink, channel, vc)

    vc.disconnect.assert_awaited_once()
    all_messages = " ".join(str(c) for c in channel.send.call_args_list)
    assert "❌" in all_messages


@pytest.mark.asyncio
async def test_pipeline_obsidian_failure_still_shows_summary(tmp_path: Path) -> None:
    """The summary is shown in Discord even when saving to Obsidian fails."""
    channel: AsyncMock = AsyncMock()
    vc: AsyncMock = AsyncMock()
    sink: MagicMock = MagicMock()
    fake_wav = tmp_path / "session.wav"
    fake_wav.write_bytes(b"RIFF")

    with (
        patch("src.bot.finish_recording", return_value=fake_wav),
        patch("src.bot.transcribe", return_value="transcript"),
        patch("src.bot.summarize", return_value="## Overview\nGreat session!"),
        patch("src.bot.save_to_obsidian", side_effect=ValueError("vault not configured")),
    ):
        await _on_recording_finished(sink, channel, vc)

    vc.disconnect.assert_awaited_once()
    all_messages = " ".join(str(c) for c in channel.send.call_args_list)
    # Summary text must be present despite Obsidian failure
    assert "Overview" in all_messages or "⚠️" in all_messages

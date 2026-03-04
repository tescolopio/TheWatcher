"""Tests for src/bot.py — on_ready, watch, unwatch, pipeline callback, and new commands."""

import io
import struct
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import discord
import pytest

from src import bot as bot_module
from src.bot import _active_recordings, _on_recording_finished


# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_channel() -> AsyncMock:
    """Return a mock channel with a properly configured typing() context manager.

    The returned channel's :meth:`send` coroutine returns an AsyncMock
    (``processing_msg``) whose ``edit`` method is also awaitable, matching
    the embed-editing pattern used by the pipeline callback.
    """
    channel: AsyncMock = AsyncMock()
    processing_msg: AsyncMock = AsyncMock()
    channel.send.return_value = processing_msg

    # Make channel.typing() work as an async context manager.
    typing_cm: AsyncMock = AsyncMock()
    typing_cm.__aenter__ = AsyncMock(return_value=None)
    typing_cm.__aexit__ = AsyncMock(return_value=False)
    channel.typing = MagicMock(return_value=typing_cm)
    return channel


def _make_interaction(
    *,
    guild_id: int = 1,
    has_guild: bool = True,
    in_voice: bool = True,
    has_channel: bool = True,
    is_admin: bool = False,
) -> MagicMock:
    """Build a minimal mock :class:`discord.Interaction`."""
    interaction: MagicMock = MagicMock(spec=discord.Interaction)
    interaction.response = AsyncMock()
    interaction.response.send_message = AsyncMock()
    interaction.response.defer = AsyncMock()
    interaction.followup = AsyncMock()
    interaction.followup.send = AsyncMock()

    if has_guild:
        guild: MagicMock = MagicMock(spec=discord.Guild)
        guild.id = guild_id
        guild.get_member = MagicMock(return_value=None)
        interaction.guild = guild
    else:
        interaction.guild = None

    if has_channel:
        interaction.channel = AsyncMock(spec=discord.TextChannel)
    else:
        interaction.channel = None

    member: MagicMock = MagicMock(spec=discord.Member)
    member.roles = []
    perms = MagicMock()
    perms.manage_guild = is_admin
    member.guild_permissions = perms

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
        patch("src.bot.get_active_recording_sessions", return_value=[]),
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
        patch("src.bot.get_active_recording_sessions", return_value=[]),
    ):
        from src.bot import on_ready

        await on_ready()  # must not raise


@pytest.mark.asyncio
async def test_on_ready_marks_orphaned_sessions_failed() -> None:
    """on_ready marks orphaned RECORDING sessions as FAILED on bot restart."""
    orphan = {"id": "orphan-001"}
    with (
        patch.object(bot_module.bot, "user", new=MagicMock()),
        patch.object(bot_module.bot.tree, "sync", new=AsyncMock(return_value=[])),
        patch("src.bot.get_active_recording_sessions", return_value=[orphan]),
        patch("src.bot.update_session") as mock_update,
    ):
        from src.bot import on_ready

        await on_ready()

    mock_update.assert_called_once_with(
        "orphan-001",
        status=bot_module.SessionStatus.FAILED,
        error_message="Bot restarted; session interrupted",
    )


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
    _active_recordings[gid] = (MagicMock(spec=discord.VoiceClient), "test-session-id")
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
    """/watch connects, creates a session, starts recording, and registers a (vc, session_id) tuple."""
    from src.bot import watch

    gid = 300
    _active_recordings.pop(gid, None)

    interaction = _make_interaction(guild_id=gid)
    mock_vc: MagicMock = MagicMock(spec=discord.VoiceClient)
    mock_vc.start_recording = MagicMock()
    interaction.user.voice.channel.connect = AsyncMock(return_value=mock_vc)

    fn = getattr(watch, "callback", watch)
    with (
        patch("src.bot.RecordingSink") as mock_sink_cls,
        patch("src.bot.create_session", return_value="new-session-id"),
        patch("src.bot.get_config", return_value=None),
    ):
        mock_sink_cls.return_value = MagicMock()
        await fn(interaction)

    assert gid in _active_recordings
    vc_stored, sid_stored = _active_recordings[gid]
    assert sid_stored == "new-session-id"
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


@pytest.mark.asyncio
async def test_watch_rejects_insufficient_disk_space(monkeypatch: pytest.MonkeyPatch) -> None:
    """/watch rejects recording when free disk space is below the threshold."""
    from src.bot import watch

    gid = 302
    _active_recordings.pop(gid, None)

    interaction = _make_interaction(guild_id=gid)

    # Patch _free_disk_mb to return less than MIN_FREE_DISK_MB
    monkeypatch.setenv("MIN_FREE_DISK_MB", "500")
    with patch("src.bot._free_disk_mb", return_value=100):
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
    _active_recordings[gid] = (mock_vc, "test-session-id")

    interaction = _make_interaction(guild_id=gid)
    fn = getattr(unwatch, "callback", unwatch)
    await fn(interaction)

    mock_vc.stop_recording.assert_called_once()
    assert gid not in _active_recordings
    interaction.response.send_message.assert_awaited_once()


# ── _on_recording_finished pipeline callback ──────────────────────────────────


@pytest.mark.asyncio
async def test_pipeline_full_success(tmp_path: Path) -> None:
    """Full pipeline runs all stages and edits the processing message to show success."""
    channel = _make_channel()
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
    channel.send.assert_awaited_once()  # single processing_msg
    processing_msg = channel.send.return_value
    # At least one edit (the success embed)
    assert processing_msg.edit.await_count >= 1
    # Final edit should show success
    last_embed = processing_msg.edit.call_args_list[-1].kwargs.get("embed")
    assert last_embed is not None
    assert "✅" in last_embed.title


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
    """Pipeline edits message with an error embed when finish_recording raises."""
    channel = _make_channel()
    vc: AsyncMock = AsyncMock()
    sink: MagicMock = MagicMock()

    with patch("src.bot.finish_recording", side_effect=RuntimeError("disk full")):
        await _on_recording_finished(sink, channel, vc)

    vc.disconnect.assert_awaited_once()
    processing_msg = channel.send.return_value
    last_embed = processing_msg.edit.call_args_list[-1].kwargs.get("embed")
    assert last_embed is not None
    assert "❌" in last_embed.title


@pytest.mark.asyncio
async def test_pipeline_transcription_failure_posts_error(tmp_path: Path) -> None:
    """Pipeline posts an error embed when transcription raises."""
    channel = _make_channel()
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
    processing_msg = channel.send.return_value
    last_embed = processing_msg.edit.call_args_list[-1].kwargs.get("embed")
    assert last_embed is not None
    assert "❌" in last_embed.title


@pytest.mark.asyncio
async def test_pipeline_summariser_failure_saves_fallback(tmp_path: Path) -> None:
    """On summarisation failure a fallback note is saved and an embed posted."""
    channel = _make_channel()
    vc: AsyncMock = AsyncMock()
    sink: MagicMock = MagicMock()
    fake_wav = tmp_path / "session.wav"
    fake_wav.write_bytes(b"RIFF")
    fallback_path = tmp_path / "fallback.md"

    with (
        patch("src.bot.finish_recording", return_value=fake_wav),
        patch("src.bot.transcribe", return_value="transcript"),
        patch("src.bot.summarize", side_effect=RuntimeError("ollama unreachable")),
        patch("src.bot.save_fallback_note", return_value=fallback_path) as mock_fallback,
    ):
        await _on_recording_finished(sink, channel, vc)

    vc.disconnect.assert_awaited_once()
    mock_fallback.assert_called_once()
    processing_msg = channel.send.return_value
    last_embed = processing_msg.edit.call_args_list[-1].kwargs.get("embed")
    assert last_embed is not None
    assert "⚠️" in last_embed.title


@pytest.mark.asyncio
async def test_pipeline_obsidian_failure_still_shows_summary(tmp_path: Path) -> None:
    """The summary is shown via embed edit even when saving to Obsidian fails."""
    channel = _make_channel()
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
    processing_msg = channel.send.return_value
    last_embed = processing_msg.edit.call_args_list[-1].kwargs.get("embed")
    assert last_embed is not None
    # Should show a warning embed (⚠️) with the summary in the description
    assert "⚠️" in last_embed.title
    assert "Overview" in (last_embed.description or "")


# ── /status command ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_status_responds_with_embed() -> None:
    """/status defers and then sends a status embed via followup."""
    from src.bot import status

    interaction = _make_interaction()
    with patch("src.bot._check_ollama", return_value=True):
        fn = getattr(status, "callback", status)
        await fn(interaction)

    interaction.response.defer.assert_awaited_once()
    interaction.followup.send.assert_awaited_once()
    call_kwargs = interaction.followup.send.call_args.kwargs
    assert "embed" in call_kwargs
    assert call_kwargs.get("ephemeral") is True


# ── /sessions command ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_sessions_shows_recent_sessions() -> None:
    """/sessions lists recent sessions as an embed."""
    from src.bot import sessions

    interaction = _make_interaction(guild_id=1)
    fake_rows = [
        {"id": "abc123def456", "status": "done", "started_at": "2026-01-01T14:00:00", "campaign": "Dragons"},
    ]
    with patch("src.bot.get_guild_sessions", return_value=fake_rows):
        fn = getattr(sessions, "callback", sessions)
        await fn(interaction)

    interaction.response.send_message.assert_awaited_once()
    kwargs = interaction.response.send_message.call_args.kwargs
    assert "embed" in kwargs


@pytest.mark.asyncio
async def test_sessions_empty_sends_message() -> None:
    """/sessions sends a plain message when no sessions exist."""
    from src.bot import sessions

    interaction = _make_interaction(guild_id=1)
    with patch("src.bot.get_guild_sessions", return_value=[]):
        fn = getattr(sessions, "callback", sessions)
        await fn(interaction)

    interaction.response.send_message.assert_awaited_once()


# ── /campaign commands ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_campaign_set_stores_value() -> None:
    """/campaign set stores the campaign name and responds."""
    from src.bot import campaign_set

    interaction = _make_interaction(guild_id=1)
    with patch("src.bot.set_config") as mock_set:
        fn = getattr(campaign_set, "callback", campaign_set)
        await fn(interaction, name="Dragons of the North")

    mock_set.assert_called_once_with(1, "campaign", "Dragons of the North")
    interaction.response.send_message.assert_awaited_once()


@pytest.mark.asyncio
async def test_campaign_clear_deletes_value() -> None:
    """/campaign clear removes the stored campaign name."""
    from src.bot import campaign_clear

    interaction = _make_interaction(guild_id=1)
    with patch("src.bot.delete_config") as mock_del:
        fn = getattr(campaign_clear, "callback", campaign_clear)
        await fn(interaction)

    mock_del.assert_called_once_with(1, "campaign")
    interaction.response.send_message.assert_awaited_once()


# ── /character commands ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_character_set_stores_name() -> None:
    """/character set registers the caller's character name."""
    from src.bot import character_set

    interaction = _make_interaction(guild_id=1)
    interaction.user.id = 99

    with patch("src.bot.set_character") as mock_set:
        fn = getattr(character_set, "callback", character_set)
        await fn(interaction, name="Aragorn")

    mock_set.assert_called_once_with(1, 99, "Aragorn")
    interaction.response.send_message.assert_awaited_once()


@pytest.mark.asyncio
async def test_character_list_shows_embed() -> None:
    """/character list shows an embed when characters are registered."""
    from src.bot import character_list

    interaction = _make_interaction(guild_id=1)
    with patch("src.bot.get_all_characters", return_value={99: "Aragorn"}):
        fn = getattr(character_list, "callback", character_list)
        await fn(interaction)

    kwargs = interaction.response.send_message.call_args.kwargs
    assert "embed" in kwargs


@pytest.mark.asyncio
async def test_character_clear_deletes_registration() -> None:
    """/character clear removes the caller's character registration."""
    from src.bot import character_clear

    interaction = _make_interaction(guild_id=1)
    interaction.user.id = 99

    with patch("src.bot.delete_character") as mock_del:
        fn = getattr(character_clear, "callback", character_clear)
        await fn(interaction)

    mock_del.assert_called_once_with(1, 99)
    interaction.response.send_message.assert_awaited_once()


# ── /config command ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_config_requires_manage_guild() -> None:
    """/config rejects users without Manage Server permission."""
    from src.bot import config_cmd

    interaction = _make_interaction(guild_id=1, is_admin=False)
    fn = getattr(config_cmd, "callback", config_cmd)
    await fn(interaction, key="ollama_model", value="llama3")

    call_kwargs = interaction.response.send_message.call_args.kwargs
    assert call_kwargs.get("ephemeral") is True


@pytest.mark.asyncio
async def test_config_sets_value_when_admin() -> None:
    """/config sets a config value when the user is a guild admin."""
    from src.bot import config_cmd

    interaction = _make_interaction(guild_id=1, is_admin=True)
    with patch("src.bot.set_config") as mock_set:
        fn = getattr(config_cmd, "callback", config_cmd)
        await fn(interaction, key="ollama_model", value="llama3")

    mock_set.assert_called_once_with(1, "ollama_model", "llama3")
    interaction.response.send_message.assert_awaited_once()


@pytest.mark.asyncio
async def test_config_rejects_unknown_key() -> None:
    """/config rejects keys that are not in the allowed-key list."""
    from src.bot import config_cmd

    interaction = _make_interaction(guild_id=1, is_admin=True)
    fn = getattr(config_cmd, "callback", config_cmd)
    await fn(interaction, key="unknown_key", value="val")

    call_kwargs = interaction.response.send_message.call_args.kwargs
    assert call_kwargs.get("ephemeral") is True


@pytest.mark.asyncio
async def test_config_reset_calls_delete() -> None:
    """/config with no value resets to default by calling delete_config."""
    from src.bot import config_cmd

    interaction = _make_interaction(guild_id=1, is_admin=True)
    with patch("src.bot.delete_config") as mock_del:
        fn = getattr(config_cmd, "callback", config_cmd)
        await fn(interaction, key="campaign", value=None)

    mock_del.assert_called_once_with(1, "campaign")


# ── /preview command ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_preview_rejects_outside_guild() -> None:
    """/preview sends an ephemeral error when used outside a guild."""
    from src.bot import preview

    interaction = _make_interaction(has_guild=False)
    fn = getattr(preview, "callback", preview)
    await fn(interaction)

    assert interaction.response.send_message.call_args.kwargs.get("ephemeral") is True


@pytest.mark.asyncio
async def test_preview_rejects_when_not_in_voice() -> None:
    """/preview sends an error when the caller is not in a voice channel."""
    from src.bot import preview

    interaction = _make_interaction(in_voice=False)
    fn = getattr(preview, "callback", preview)
    await fn(interaction)

    assert interaction.response.send_message.call_args.kwargs.get("ephemeral") is True


@pytest.mark.asyncio
async def test_preview_starts_and_auto_stops(tmp_path: Path) -> None:
    """/preview connects, starts a 5-second recording and posts an embed."""
    from src.bot import _preview_tasks, preview

    gid = 888
    _preview_tasks.discard(gid)

    interaction = _make_interaction(guild_id=gid)
    mock_vc: MagicMock = MagicMock(spec=discord.VoiceClient)
    mock_vc.start_recording = MagicMock()
    mock_vc.stop_recording = MagicMock()
    interaction.user.voice.channel.connect = AsyncMock(return_value=mock_vc)

    fn = getattr(preview, "callback", preview)
    with (
        patch("src.bot.RecordingSink") as mock_sink_cls,
        patch("asyncio.create_task"),
    ):
        mock_sink_cls.return_value = MagicMock()
        await fn(interaction)

    mock_vc.start_recording.assert_called_once()
    interaction.response.send_message.assert_awaited_once()
    _preview_tasks.discard(gid)

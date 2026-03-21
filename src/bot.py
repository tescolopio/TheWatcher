"""RPG Watcher – Discord bot entry point.

Slash commands provided:
  /watch           – join a voice channel and start recording (v0.1+)
  /unwatch         – stop recording and run the full pipeline (v0.1+)
  /status          – show bot health, Ollama connectivity, disk space (v0.3+)
  /sessions        – list recent recording sessions for this server (v0.3+)
  /campaign set    – store the active campaign name for this server (v0.4+)
  /campaign clear  – remove the active campaign name (v0.4+)
  /config          – server-admin config override (v0.4+)
  /character set   – register a player's in-game character name (v0.5+)
  /character list  – list all registered character names (v0.5+)
  /character clear – remove a character name registration (v0.5+)
  /preview         – record a 5-second mic check (v0.6+)

Run with:
    python -m src.bot
or after installing the package:
    rpgwatcher
"""

import asyncio
import json
import logging
import os
import shutil
import urllib.parse
from pathlib import Path
from typing import Optional, Union

import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

from src.database import (
    SessionStatus,
    create_session,
    delete_character,
    delete_config,
    get_active_recording_sessions,
    get_all_characters,
    get_config,
    get_guild_sessions,
    init_db,
    set_character,
    set_config,
    update_session,
)
from src.obsidian import save_fallback_note, save_to_obsidian
from src.recorder import RecordingSink, extract_per_speaker_audio, finish_recording
from src.summarizer import summarize
from src.transcriber import transcribe

load_dotenv()

# ── Logging ───────────────────────────────────────────────────────────────────


class _JsonFormatter(logging.Formatter):
    """Compact JSON log formatter — used when ``LOG_FORMAT=json``."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        cid = getattr(record, "correlation_id", None)
        if cid:
            payload["correlation_id"] = cid
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload)


_LOG_FORMAT = os.getenv("LOG_FORMAT", "text")
if _LOG_FORMAT == "json":
    _handler = logging.StreamHandler()
    _handler.setFormatter(_JsonFormatter())
    logging.basicConfig(level=logging.INFO, handlers=[_handler])
else:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

logger = logging.getLogger(__name__)

# ── Database ─────────────────────────────────────────────────────────────────

init_db()

# ── Constants ─────────────────────────────────────────────────────────────────

_MIN_FREE_DISK_MB = int(os.getenv("MIN_FREE_DISK_MB", "500"))

# ── Bot setup ─────────────────────────────────────────────────────────────────

intents = discord.Intents.default()
intents.voice_states = True

bot = commands.Bot(command_prefix="!", intents=intents)

# guild_id → (VoiceClient, session_id)
_active_recordings: dict[int, tuple[discord.VoiceClient, str]] = {}

# guild_id present while a /preview is in progress
_preview_tasks: set[int] = set()


# ── Events ────────────────────────────────────────────────────────────────────


@bot.event
async def on_ready() -> None:
    user = bot.user
    if user is not None:
        logger.info("Logged in as %s (ID: %s)", user, user.id)
    # Mark orphaned sessions from a previous crash as FAILED.
    orphaned = get_active_recording_sessions()
    for s in orphaned:
        update_session(
            s["id"],
            status=SessionStatus.FAILED,
            error_message="Bot restarted; session interrupted",
        )
    if orphaned:
        logger.warning("Marked %d orphaned session(s) as failed.", len(orphaned))
    try:
        synced = await bot.tree.sync()
        logger.info("Synced %d slash command(s).", len(synced))
    except Exception as exc:  # pragma: no cover
        logger.error("Failed to sync commands: %s", exc)


# ── Helpers ───────────────────────────────────────────────────────────────────


def _free_disk_mb(directory: Optional[str] = None) -> int:
    """Return available disk space in megabytes for *directory*."""
    path = directory or os.getenv("RECORDINGS_DIR", "/tmp/rpgwatcher_recordings")
    check_path = path if os.path.exists(path) else "/"
    return int(shutil.disk_usage(check_path).free // (1024 * 1024))


def _has_required_role(interaction: discord.Interaction) -> bool:
    """Return True if the user has an allowed role or no restriction is configured."""
    allowed_str = os.getenv("ALLOWED_ROLE_IDS", "").strip()
    if not allowed_str:
        return True
    allowed_ids = {int(r) for r in allowed_str.split(",") if r.strip().isdigit()}
    member = interaction.user
    if not isinstance(member, discord.Member):
        return False
    return any(role.id in allowed_ids for role in member.roles)


def _make_embed(title: str, description: str, color: discord.Color) -> discord.Embed:
    return discord.Embed(title=title, description=description, color=color)


def _whisper_backend_label() -> str:
    cpp = os.getenv("WHISPER_CPP_PATH", "")
    if cpp and Path(cpp).is_file():
        return f"whisper.cpp (`{cpp}`)"
    return f"openai-whisper (model: **{os.getenv('WHISPER_MODEL', 'base')}**)"


def _obsidian_deep_link(note_path: Path) -> Optional[str]:
    vault_path = os.getenv("OBSIDIAN_VAULT_PATH", "")
    if not vault_path:
        return None
    try:
        relative = note_path.relative_to(vault_path)
        vault_name = Path(vault_path).name
        return (
            f"obsidian://open?vault={urllib.parse.quote(vault_name)}"
            f"&file={urllib.parse.quote(str(relative))}"
        )
    except ValueError:
        return None


async def _check_ollama(base_url: str) -> bool:
    try:
        import ollama as _ollama

        await asyncio.to_thread(lambda: _ollama.Client(host=base_url).list())
        return True
    except Exception:
        return False


# ── Pipeline callback ─────────────────────────────────────────────────────────


async def _on_recording_finished(
    sink: RecordingSink,
    channel: Union[discord.abc.Messageable, None],
    vc: discord.VoiceClient,
    session_id: str = "",
    guild_id: int = 0,
) -> None:
    """Full post-recording pipeline: save → transcribe → summarise → save notes.

    Uses rich Embeds for status (v0.4).  A single 'processing' message is sent
    and edited through each pipeline stage.  On final failure the raw transcript
    is saved as a fallback Obsidian note (v0.3).
    """
    cid = f"[{session_id[:6]}]" if session_id else "[pipeline]"

    if channel is None:  # pragma: no cover
        logger.error("%s channel is None; aborting pipeline", cid)
        await vc.disconnect()
        return

    if session_id:
        update_session(session_id, status=SessionStatus.PROCESSING)

    # Fetch guild-level context (campaign, characters) ─────────────────────
    campaign: Optional[str] = None
    chars: dict[int, str] = {}
    if guild_id:
        campaign = get_config(guild_id, "campaign")
        chars = get_all_characters(guild_id)

    # Send initial status embed ──────────────────────────────────────────────
    processing_msg = await channel.send(
        embed=_make_embed("⚙️ Processing…", "🔄 Saving audio…", discord.Color.blue())
    )

    # Stage 1 – Save audio ───────────────────────────────────────────────────
    audio_path: Optional[Path] = None
    try:
        async with channel.typing():  # type: ignore[attr-defined]
            audio_path = await asyncio.to_thread(finish_recording, sink)
        if session_id:
            update_session(session_id, wav_path=str(audio_path))
        logger.info("%s Audio saved to %s", cid, audio_path)
    except Exception as exc:
        logger.exception("%s Failed to save recording", cid)
        if session_id:
            update_session(
                session_id,
                status=SessionStatus.FAILED,
                error_message=f"Save failed: {exc}",
            )
        await processing_msg.edit(
            embed=_make_embed("❌ Recording Failed", str(exc), discord.Color.red())
        )
        await vc.disconnect()
        return

    # Stage 2 – Transcribe ───────────────────────────────────────────────────
    transcript = ""
    speakers_list: Optional[list[str]] = None
    try:
        if chars:
            # v0.5 per-speaker transcription
            await processing_msg.edit(
                embed=_make_embed(
                    "⚙️ Processing…",
                    "🗣️ Transcribing per speaker…",
                    discord.Color.blue(),
                )
            )
            async with channel.typing():  # type: ignore[attr-defined]
                per_speaker_wavs = await asyncio.to_thread(
                    extract_per_speaker_audio, sink, audio_path.parent
                )
            segments: list[str] = []
            for uid_str, spk_path in per_speaker_wavs.items():
                uid_int = int(uid_str)
                name = chars.get(uid_int, f"Speaker_{uid_str}")
                async with channel.typing():  # type: ignore[attr-defined]
                    seg = await asyncio.to_thread(transcribe, spk_path)
                segments.append(f"[{name}]: {seg}")
            transcript = "\n".join(segments)
            speakers_list = list(chars.values())
        else:
            await processing_msg.edit(
                embed=_make_embed(
                    "⚙️ Processing…",
                    "🗣️ Transcribing with Whisper…",
                    discord.Color.blue(),
                )
            )
            async with channel.typing():  # type: ignore[attr-defined]
                transcript = await asyncio.to_thread(transcribe, audio_path)
        if session_id:
            update_session(session_id, transcript=transcript)
        logger.info("%s Transcription complete (%d chars)", cid, len(transcript))
    except Exception as exc:
        logger.exception("%s Transcription failed", cid)
        if session_id:
            update_session(session_id, status=SessionStatus.FAILED, error_message=f"Transcription: {exc}")
        await processing_msg.edit(
            embed=_make_embed("❌ Transcription Failed", str(exc), discord.Color.red())
        )
        await vc.disconnect()
        return

    # Stage 3 – Summarise (with retry + fallback) ────────────────────────────
    await processing_msg.edit(
        embed=_make_embed("⚙️ Processing…", "🧠 Generating summary with Ollama…", discord.Color.blue())
    )
    summary_md: Optional[str] = None
    try:
        async with channel.typing():  # type: ignore[attr-defined]
            summary_md = await asyncio.to_thread(summarize, transcript, speakers_list)
        if session_id:
            update_session(session_id, summary=summary_md)
        logger.info("%s Summary generated (%d chars)", cid, len(summary_md))
    except Exception as exc:
        logger.exception("%s Summarisation failed — saving fallback note", cid)
        if session_id:
            update_session(session_id, status=SessionStatus.FAILED, error_message=f"Summarise: {exc}")
        try:
            fallback_path = await asyncio.to_thread(
                save_fallback_note, transcript, str(exc), campaign
            )
            if session_id:
                update_session(session_id, note_path=str(fallback_path))
            await processing_msg.edit(
                embed=_make_embed(
                    "⚠️ Summary Failed — Transcript Saved",
                    f"Could not generate summary: {exc}\n\nRaw transcript saved to:\n`{fallback_path}`",
                    discord.Color.yellow(),
                )
            )
        except Exception as fb_exc:
            await processing_msg.edit(
                embed=_make_embed(
                    "❌ Pipeline Failed",
                    f"Summarisation failed: {exc}\nFallback save also failed: {fb_exc}",
                    discord.Color.red(),
                )
            )
        await vc.disconnect()
        return

    # Stage 4 – Save to Obsidian ──────────────────────────────────────────────
    try:
        chars_names = list(chars.values()) if chars else None
        note_path = await asyncio.to_thread(
            save_to_obsidian, summary_md, campaign, chars_names
        )
        if session_id:
            update_session(
                session_id,
                status=SessionStatus.DONE,
                note_path=str(note_path),
            )

        # Build success embed with paginated preview
        preview = summary_md[:3900] + ("…" if len(summary_md) > 3900 else "")
        deep_link = _obsidian_deep_link(note_path)

        result_embed = discord.Embed(
            title="✅ Session Summary Ready",
            description=f"Saved to `{note_path}`\n\n```markdown\n{preview}\n```",
            color=discord.Color.green(),
        )
        if campaign:
            result_embed.set_footer(text=f"Campaign: {campaign}")

        # Button to open note in Obsidian
        view: Optional[discord.ui.View] = None
        if deep_link:
            v = discord.ui.View()
            v.add_item(
                discord.ui.Button(
                    label="Open in Obsidian",
                    url=deep_link,
                    style=discord.ButtonStyle.link,
                )
            )
            view = v

        await processing_msg.edit(embed=result_embed, view=view)

    except Exception as exc:
        logger.exception("%s Failed to save note to Obsidian", cid)
        if session_id:
            update_session(session_id, status=SessionStatus.FAILED, error_message=f"Obsidian: {exc}")
        preview = summary_md[:3500] + ("…" if len(summary_md) > 3500 else "")
        await processing_msg.edit(
            embed=_make_embed(
                "⚠️ Summary Ready — Obsidian Save Failed",
                f"Could not save to Obsidian: {exc}\n\n```markdown\n{preview}\n```",
                discord.Color.yellow(),
            )
        )

    await vc.disconnect()
    logger.info("%s Pipeline complete", cid)


# ── Preview pipeline callback ─────────────────────────────────────────────────


async def _on_preview_finished(
    sink: RecordingSink,
    channel: Union[discord.abc.Messageable, None],
    vc: discord.VoiceClient,
    guild_id: int = 0,
) -> None:
    """Save preview audio and send it directly to the channel."""
    _preview_tasks.discard(guild_id)
    if channel is None:
        await vc.disconnect()
        return
    try:
        audio_path = await asyncio.to_thread(finish_recording, sink)
        await channel.send(
            "🎙️ Here's your 5-second preview — check your mic level!",
            file=discord.File(str(audio_path), filename="preview.wav"),
        )
    except Exception as exc:
        await channel.send(f"❌ Preview failed: {exc}")
    finally:
        await vc.disconnect()


async def _auto_stop_preview(vc: discord.VoiceClient, guild_id: int, delay: float = 5.0) -> None:
    """Stop preview recording after *delay* seconds."""
    await asyncio.sleep(delay)
    if guild_id in _preview_tasks:
        vc.stop_recording()


# ── /watch ────────────────────────────────────────────────────────────────────


@bot.tree.command(name="watch", description="Start recording the current voice channel.")
async def watch(interaction: discord.Interaction) -> None:
    """Join the caller's voice channel and begin recording."""
    if interaction.guild is None:
        await interaction.response.send_message(
            "This command can only be used inside a server.", ephemeral=True
        )
        return

    guild_id = interaction.guild.id

    # v0.7 – role-based access control
    if not _has_required_role(interaction):
        await interaction.response.send_message(
            "You do not have the required role to use this command.", ephemeral=True
        )
        return

    if guild_id in _active_recordings or guild_id in _preview_tasks:
        await interaction.response.send_message(
            "Already recording in this server. Use `/unwatch` to stop first.", ephemeral=True
        )
        return

    member = interaction.user
    if (
        not isinstance(member, discord.Member)
        or member.voice is None
        or member.voice.channel is None
    ):
        await interaction.response.send_message(
            "You must be in a voice channel to start recording.", ephemeral=True
        )
        return

    voice_channel = member.voice.channel

    channel = interaction.channel
    if channel is None:
        await interaction.response.send_message(
            "Could not determine the text channel.", ephemeral=True
        )
        return

    # v0.3 – disk space guard
    recordings_dir = os.getenv("RECORDINGS_DIR", "/tmp/rpgwatcher_recordings")
    if _free_disk_mb(recordings_dir) < _MIN_FREE_DISK_MB:
        await interaction.response.send_message(
            f"⚠️ Not enough free disk space (need {_MIN_FREE_DISK_MB} MB). "
            "Free up space and try again.",
            ephemeral=True,
        )
        return

    try:
        vc = await voice_channel.connect()
    except discord.ClientException as exc:
        await interaction.response.send_message(
            f"Could not join voice channel: {exc}", ephemeral=True
        )
        return

    # v0.4 – resolve campaign from DB or env
    campaign = get_config(guild_id, "campaign")

    # v0.3 – create session row
    session_id = create_session(
        guild_id=guild_id,
        channel_id=getattr(channel, "id", None),
        voice_channel=voice_channel.name,
        campaign=campaign,
    )

    sink = RecordingSink()
    vc.start_recording(sink, _on_recording_finished, channel, vc, session_id, guild_id)
    _active_recordings[guild_id] = (vc, session_id)

    embed = discord.Embed(
        title="🎙️ Recording Started",
        description=(
            f"Recording **{voice_channel.name}**.\n"
            + (f"Campaign: **{campaign}**\n" if campaign else "")
            + "\nUse `/unwatch` when the session is over."
        ),
        color=discord.Color.blue(),
    )
    await interaction.response.send_message(embed=embed)
    logger.info(
        "Recording started — guild %d, channel '%s', session %s",
        guild_id,
        voice_channel.name,
        session_id,
    )


# ── /unwatch ──────────────────────────────────────────────────────────────────


@bot.tree.command(name="unwatch", description="Stop recording and generate a session summary.")
async def unwatch(interaction: discord.Interaction) -> None:
    """Stop the active recording; trigger the transcription / summary pipeline."""
    if interaction.guild is None:
        await interaction.response.send_message(
            "This command can only be used inside a server.", ephemeral=True
        )
        return

    guild_id = interaction.guild.id

    if guild_id not in _active_recordings:
        await interaction.response.send_message(
            "No active recording found in this server.", ephemeral=True
        )
        return

    vc, session_id = _active_recordings.pop(guild_id)
    vc.stop_recording()  # triggers _on_recording_finished asynchronously

    await interaction.response.send_message(
        embed=_make_embed(
            "⏹️ Recording Stopped",
            "Processing audio in the background… I'll post the summary here when done.",
            discord.Color.yellow(),
        )
    )
    logger.info("Recording stopped — guild %d, session %s", guild_id, session_id)


# ── /status ───────────────────────────────────────────────────────────────────


@bot.tree.command(name="status", description="Show bot health, Ollama connectivity, and disk info.")
async def status(interaction: discord.Interaction) -> None:
    """Display runtime status information."""
    await interaction.response.defer(ephemeral=True)

    latency_ms = round(bot.latency * 1000)
    base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    ollama_ok = await _check_ollama(base_url)
    vault_path = os.getenv("OBSIDIAN_VAULT_PATH", "")
    recordings_dir = os.getenv("RECORDINGS_DIR", "/tmp/rpgwatcher_recordings")
    disk_mb = _free_disk_mb(recordings_dir)
    disk_emoji = "🟢" if disk_mb >= _MIN_FREE_DISK_MB else "🔴"

    embed = discord.Embed(title="📊 RPG Watcher Status", color=discord.Color.blurple())
    embed.add_field(name="🏓 Latency", value=f"{latency_ms} ms", inline=True)
    embed.add_field(
        name="🤖 Ollama",
        value=f"{'✅' if ollama_ok else '❌'} `{base_url}`",
        inline=True,
    )
    embed.add_field(
        name="🗣️ Whisper Backend",
        value=_whisper_backend_label(),
        inline=False,
    )
    embed.add_field(
        name="📓 Vault",
        value=f"`{vault_path}`" if vault_path else "❌ Not configured",
        inline=False,
    )
    embed.add_field(
        name=f"{disk_emoji} Free Disk",
        value=f"{disk_mb:,} MB (threshold: {_MIN_FREE_DISK_MB} MB)",
        inline=True,
    )
    embed.add_field(
        name="🎙️ Active Recordings",
        value=str(len(_active_recordings)),
        inline=True,
    )

    await interaction.followup.send(embed=embed, ephemeral=True)


# ── /sessions ────────────────────────────────────────────────────────────────


@bot.tree.command(name="sessions", description="List recent recording sessions for this server.")
async def sessions(interaction: discord.Interaction) -> None:
    """Show the 10 most recent sessions for this guild."""
    if interaction.guild is None:
        await interaction.response.send_message(
            "This command can only be used inside a server.", ephemeral=True
        )
        return

    rows = get_guild_sessions(interaction.guild.id, limit=10)
    if not rows:
        await interaction.response.send_message(
            "No sessions recorded for this server yet.", ephemeral=True
        )
        return

    _STATUS_EMOJI = {
        SessionStatus.RECORDING: "🔴",
        SessionStatus.PROCESSING: "🟡",
        SessionStatus.DONE: "✅",
        SessionStatus.FAILED: "❌",
    }

    lines: list[str] = []
    for row in rows:
        emoji = _STATUS_EMOJI.get(row["status"], "❓")
        sid_short = row["id"][:8]
        ts = row["started_at"][:16].replace("T", " ")
        campaign_tag = f" [{row['campaign']}]" if row.get("campaign") else ""
        lines.append(f"{emoji} `{sid_short}` {ts}{campaign_tag}")

    embed = discord.Embed(
        title="🗂️ Recent Sessions",
        description="\n".join(lines),
        color=discord.Color.blurple(),
    )
    await interaction.response.send_message(embed=embed, ephemeral=True)


# ── /campaign ────────────────────────────────────────────────────────────────

_campaign_group = app_commands.Group(name="campaign", description="Campaign name management")


@_campaign_group.command(name="set", description="Set the active campaign name for this server.")
async def campaign_set(interaction: discord.Interaction, name: str) -> None:
    """Store *name* as the current campaign for future sessions."""
    if interaction.guild is None:
        await interaction.response.send_message(
            "This command can only be used inside a server.", ephemeral=True
        )
        return
    set_config(interaction.guild.id, "campaign", name)
    await interaction.response.send_message(
        f"📖 Campaign set to **{name}**. Future sessions will be filed under this campaign.",
        ephemeral=True,
    )


@_campaign_group.command(name="clear", description="Clear the active campaign name for this server.")
async def campaign_clear(interaction: discord.Interaction) -> None:
    """Remove the current campaign setting."""
    if interaction.guild is None:
        await interaction.response.send_message(
            "This command can only be used inside a server.", ephemeral=True
        )
        return
    delete_config(interaction.guild.id, "campaign")
    await interaction.response.send_message("📖 Campaign cleared.", ephemeral=True)


bot.tree.add_command(_campaign_group)


# ── /character ───────────────────────────────────────────────────────────────

_character_group = app_commands.Group(name="character", description="Player character registry")


@_character_group.command(name="set", description="Register your in-game character name.")
async def character_set(interaction: discord.Interaction, name: str) -> None:
    """Associate the calling user with *name* in the character registry."""
    if interaction.guild is None:
        await interaction.response.send_message(
            "This command can only be used inside a server.", ephemeral=True
        )
        return
    user = interaction.user
    set_character(interaction.guild.id, user.id, name)
    await interaction.response.send_message(
        f"🧙 Character set to **{name}**. Your transcript segments will be labelled with this name.",
        ephemeral=True,
    )


@_character_group.command(name="list", description="List all registered characters in this server.")
async def character_list(interaction: discord.Interaction) -> None:
    """Show every player → character mapping for this guild."""
    if interaction.guild is None:
        await interaction.response.send_message(
            "This command can only be used inside a server.", ephemeral=True
        )
        return
    chars = get_all_characters(interaction.guild.id)
    if not chars:
        await interaction.response.send_message(
            "No characters registered yet. Use `/character set <name>` to register.",
            ephemeral=True,
        )
        return
    guild = interaction.guild
    lines: list[str] = []
    for uid, cname in chars.items():
        member = guild.get_member(uid)
        display = member.display_name if member else f"<@{uid}>"
        lines.append(f"• **{cname}** — {display}")
    embed = discord.Embed(
        title="🧙 Registered Characters",
        description="\n".join(lines),
        color=discord.Color.blurple(),
    )
    await interaction.response.send_message(embed=embed, ephemeral=True)


@_character_group.command(name="clear", description="Remove your character name registration.")
async def character_clear(interaction: discord.Interaction) -> None:
    """Remove the calling user's character registration."""
    if interaction.guild is None:
        await interaction.response.send_message(
            "This command can only be used inside a server.", ephemeral=True
        )
        return
    delete_character(interaction.guild.id, interaction.user.id)
    await interaction.response.send_message("🧙 Character registration removed.", ephemeral=True)


bot.tree.add_command(_character_group)


# ── /config ───────────────────────────────────────────────────────────────────


@bot.tree.command(name="config", description="(Admin) Set per-server configuration overrides.")
@app_commands.describe(
    key="Config key: ollama_model | notes_folder | campaign | silence_threshold_db",
    value="New value (leave empty to reset to global default)",
)
async def config_cmd(
    interaction: discord.Interaction,
    key: str,
    value: Optional[str] = None,
) -> None:
    """Allow guild admins to override bot configuration without editing .env."""
    if interaction.guild is None:
        await interaction.response.send_message(
            "This command can only be used inside a server.", ephemeral=True
        )
        return

    member = interaction.user
    if not isinstance(member, discord.Member) or not member.guild_permissions.manage_guild:
        await interaction.response.send_message(
            "You need **Manage Server** permission to use this command.", ephemeral=True
        )
        return

    allowed_keys = {"ollama_model", "notes_folder", "campaign", "silence_threshold_db"}
    if key not in allowed_keys:
        await interaction.response.send_message(
            f"Unknown key `{key}`. Valid keys: {', '.join(sorted(allowed_keys))}",
            ephemeral=True,
        )
        return

    if value is None:
        delete_config(interaction.guild.id, key)
        await interaction.response.send_message(
            f"⚙️ `{key}` reset to global default.", ephemeral=True
        )
    else:
        set_config(interaction.guild.id, key, value)
        await interaction.response.send_message(
            f"⚙️ `{key}` set to **{value}**.", ephemeral=True
        )


# ── /preview ──────────────────────────────────────────────────────────────────


@bot.tree.command(name="preview", description="Record a 5-second clip for a mic check.")
async def preview(interaction: discord.Interaction) -> None:
    """Record 5 seconds of audio and send it back to the channel."""
    if interaction.guild is None:
        await interaction.response.send_message(
            "This command can only be used inside a server.", ephemeral=True
        )
        return

    guild_id = interaction.guild.id

    if guild_id in _active_recordings or guild_id in _preview_tasks:
        await interaction.response.send_message(
            "A recording or preview is already in progress.", ephemeral=True
        )
        return

    member = interaction.user
    if (
        not isinstance(member, discord.Member)
        or member.voice is None
        or member.voice.channel is None
    ):
        await interaction.response.send_message(
            "You must be in a voice channel to use /preview.", ephemeral=True
        )
        return

    channel = interaction.channel
    if channel is None:
        await interaction.response.send_message(
            "Could not determine the text channel.", ephemeral=True
        )
        return

    voice_channel = member.voice.channel
    try:
        vc = await voice_channel.connect()
    except discord.ClientException as exc:
        await interaction.response.send_message(
            f"Could not join voice channel: {exc}", ephemeral=True
        )
        return

    _preview_tasks.add(guild_id)
    sink = RecordingSink()
    vc.start_recording(sink, _on_preview_finished, channel, vc, guild_id)
    asyncio.create_task(_auto_stop_preview(vc, guild_id))

    await interaction.response.send_message(
        embed=_make_embed(
            "🎙️ Recording Preview",
            "Recording for 5 seconds… I'll send the clip when done.",
            discord.Color.blue(),
        )
    )


# ── Entry point ───────────────────────────────────────────────────────────────


def main() -> None:
    """Start the bot using the ``DISCORD_BOT_TOKEN`` environment variable."""
    token = os.getenv("DISCORD_BOT_TOKEN")
    if not token:
        raise ValueError(
            "DISCORD_BOT_TOKEN environment variable is not set. "
            "Copy .env.example to .env and fill in your token."
        )
    bot.run(token)


if __name__ == "__main__":  # pragma: no cover
    main()

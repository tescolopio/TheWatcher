"""TheWatcher – Discord bot entry point.

Provides two slash commands:
  /watch   – joins the caller's voice channel and starts recording.
  /unwatch – stops recording, runs the full pipeline (transcribe → summarise →
             save to Obsidian), and posts the summary in the text channel.

Run with:
    python -m src.bot
or after installing the package:
    thewatcher
"""

import asyncio
import logging
import os
from pathlib import Path
from typing import Union

import discord
from discord.ext import commands
from dotenv import load_dotenv

from src.obsidian import save_to_obsidian
from src.recorder import RecordingSink, finish_recording
from src.summarizer import summarize
from src.transcriber import transcribe

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# ── Bot setup ────────────────────────────────────────────────────────────────

intents = discord.Intents.default()
intents.voice_states = True

bot = commands.Bot(command_prefix="!", intents=intents)

# guild_id → active VoiceClient
_active_recordings: dict[int, discord.VoiceClient] = {}


# ── Events ───────────────────────────────────────────────────────────────────


@bot.event
async def on_ready() -> None:
    user = bot.user
    if user is not None:
        logger.info("Logged in as %s (ID: %s)", user, user.id)
    try:
        synced = await bot.tree.sync()
        logger.info("Synced %d slash command(s).", len(synced))
    except Exception as exc:  # pragma: no cover
        logger.error("Failed to sync commands: %s", exc)


# ── Pipeline callback ─────────────────────────────────────────────────────────


async def _on_recording_finished(
    sink: RecordingSink,
    channel: Union[discord.abc.Messageable, None],
    vc: discord.VoiceClient,
) -> None:
    """Full post-recording pipeline: save → transcribe → summarise → save to Obsidian."""
    if channel is None:  # pragma: no cover
        logger.error("Recording finished but channel reference is None; cannot post status.")
        await vc.disconnect()
        return
    await channel.send("🔄 Saving audio…")
    try:
        audio_path: Path = await asyncio.to_thread(finish_recording, sink)
    except Exception as exc:
        logger.exception("Failed to save recording.")
        await channel.send(f"❌ Failed to save recording: {exc}")
        await vc.disconnect()
        return

    await channel.send("🗣️ Transcribing with Whisper…")
    try:
        transcript: str = await asyncio.to_thread(transcribe, audio_path)
    except Exception as exc:
        logger.exception("Transcription failed.")
        await channel.send(f"❌ Transcription failed: {exc}")
        await vc.disconnect()
        return

    await channel.send("🧠 Generating summary with Ollama…")
    try:
        summary_md: str = await asyncio.to_thread(summarize, transcript)
    except Exception as exc:
        logger.exception("Summarisation failed.")
        await channel.send(f"❌ Summarisation failed: {exc}")
        await vc.disconnect()
        return

    try:
        note_path = await asyncio.to_thread(save_to_obsidian, summary_md)
        preview = summary_md[:1500] + ("…" if len(summary_md) > 1500 else "")
        await channel.send(
            f"✅ Session summary saved to Obsidian:\n`{note_path}`\n\n"
            f"**Preview:**\n```markdown\n{preview}\n```"
        )
    except Exception as exc:
        logger.exception("Failed to save note to Obsidian.")
        preview = summary_md[:1500] + ("…" if len(summary_md) > 1500 else "")
        await channel.send(
            f"⚠️ Summary generated but could not be saved to Obsidian: {exc}\n\n"
            f"**Summary:**\n```markdown\n{preview}\n```"
        )

    await vc.disconnect()
    logger.info("Pipeline complete.")


# ── Slash commands ────────────────────────────────────────────────────────────


@bot.tree.command(name="watch", description="Start recording the current voice channel.")
async def watch(interaction: discord.Interaction) -> None:
    """Join the caller's voice channel and begin recording."""
    if interaction.guild is None:
        await interaction.response.send_message(
            "This command can only be used inside a server.", ephemeral=True
        )
        return

    guild_id = interaction.guild.id

    if guild_id in _active_recordings:
        await interaction.response.send_message(
            "Already recording in this server. Use `/unwatch` to stop first.", ephemeral=True
        )
        return

    member = interaction.user
    if not isinstance(member, discord.Member) or member.voice is None or member.voice.channel is None:
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

    try:
        vc = await voice_channel.connect()
    except discord.ClientException as exc:
        await interaction.response.send_message(
            f"Could not join voice channel: {exc}", ephemeral=True
        )
        return

    sink = RecordingSink()
    vc.start_recording(sink, _on_recording_finished, channel, vc)
    _active_recordings[guild_id] = vc

    await interaction.response.send_message(
        f"🎙️ Recording started in **{voice_channel.name}**.\n"
        "Use `/unwatch` when the session is over to generate a summary."
    )
    logger.info("Recording started in guild %d, channel '%s'.", guild_id, voice_channel.name)


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

    vc = _active_recordings.pop(guild_id)
    vc.stop_recording()  # triggers _on_recording_finished asynchronously

    await interaction.response.send_message(
        "⏹️ Recording stopped. Processing audio in the background…"
    )
    logger.info("Recording stopped for guild %d.", guild_id)


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


if __name__ == "__main__":
    main()

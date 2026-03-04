"""Write session summary Markdown notes directly into an Obsidian vault.

Notes are saved under ``<OBSIDIAN_VAULT_PATH>/<OBSIDIAN_NOTES_FOLDER>/`` as
dated Markdown files with YAML front-matter.  If a note for today already
exists a numeric suffix is appended to avoid overwriting.

v0.3 addition: ``save_fallback_note`` — writes the raw transcript to a note
  tagged ``#needs-summary`` when the Ollama step fails.

v0.4 addition: ``save_to_obsidian`` accepts an optional *campaign* name that
  creates a campaign sub-folder and tags the note accordingly.

v0.5 addition: ``save_to_obsidian`` accepts an optional *characters* list that
  is written into the note YAML front-matter.
"""

import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


def _get_notes_dir(campaign: Optional[str] = None) -> Path:
    """Resolve and create the notes directory inside the Obsidian vault.

    If *campaign* is provided the notes are placed in a campaign sub-folder.

    Returns:
        Path to the (campaign) notes subdirectory.

    Raises:
        ValueError: If ``OBSIDIAN_VAULT_PATH`` is not configured.
    """
    vault_path = os.getenv("OBSIDIAN_VAULT_PATH", "")
    if not vault_path:
        raise ValueError(
            "OBSIDIAN_VAULT_PATH environment variable is not set. "
            "Set it to the root directory of your Obsidian vault."
        )
    notes_folder = os.getenv("OBSIDIAN_NOTES_FOLDER", "Session Notes")
    notes_dir = Path(vault_path) / notes_folder
    if campaign:
        notes_dir = notes_dir / campaign
    notes_dir.mkdir(parents=True, exist_ok=True)
    return notes_dir


def _unique_note_path(notes_dir: Path, date_str: str) -> Path:
    """Return a path for a new note that does not collide with an existing one.

    Args:
        notes_dir: Directory in which to create the note.
        date_str:  ISO date string used as part of the filename (``YYYY-MM-DD``).

    Returns:
        A :class:`~pathlib.Path` guaranteed not to exist yet.
    """
    candidate = notes_dir / f"Session - {date_str}.md"
    counter = 1
    while candidate.exists():
        counter += 1
        candidate = notes_dir / f"Session - {date_str} ({counter}).md"
    return candidate


def save_to_obsidian(
    summary_markdown: str,
    campaign: Optional[str] = None,
    characters: Optional[list[str]] = None,
) -> Path:
    """Write *summary_markdown* as a new note in the configured Obsidian vault.

    The note is prefixed with YAML front-matter containing the creation date,
    optional campaign name, optional character list, and relevant tags so that
    Obsidian can index it immediately.

    Args:
        summary_markdown: Markdown text produced by the summariser.
        campaign:         Optional campaign name for sub-folder placement and
                          tagging.
        characters:       Optional list of character names to include in YAML
                          front-matter (v0.5 speaker identification).

    Returns:
        Absolute path of the newly created note file.
    """
    notes_dir = _get_notes_dir(campaign=campaign)
    now = datetime.now()
    date_str = now.strftime("%Y-%m-%d")
    datetime_str = now.strftime("%Y-%m-%d %H:%M")

    note_path = _unique_note_path(notes_dir, date_str)

    # Build YAML front-matter
    campaign_line = f"campaign: {campaign}\n" if campaign else ""

    chars_yaml = ""
    if characters:
        chars_yaml = "characters:\n" + "".join(f"  - {c}\n" for c in characters)

    campaign_tag = f"  - {campaign}\n" if campaign else ""

    content = (
        "---\n"
        f"date: {datetime_str}\n"
        f"{campaign_line}"
        f"{chars_yaml}"
        "tags:\n"
        "  - session-notes\n"
        "  - ttrpg\n"
        f"{campaign_tag}"
        "---\n\n"
        f"{summary_markdown}\n"
    )

    note_path.write_text(content, encoding="utf-8")
    logger.info("Saved session note to %s", note_path)
    return note_path


def save_fallback_note(
    transcript: str,
    error: str,
    campaign: Optional[str] = None,
) -> Path:
    """Save the raw transcript as a fallback note when summarisation fails.

    The note is tagged ``#needs-summary`` so it can be found and re-processed
    manually.  This ensures that recorded session data is never silently
    discarded even when the Ollama step is unavailable.

    Args:
        transcript: Raw transcript text from Whisper.
        error:      Description of the error that caused summarisation to fail.
        campaign:   Optional campaign name for sub-folder placement.

    Returns:
        Absolute path of the fallback note file.
    """
    notes_dir = _get_notes_dir(campaign=campaign)
    now = datetime.now()
    date_str = now.strftime("%Y-%m-%d")
    datetime_str = now.strftime("%Y-%m-%d %H:%M")

    note_path = _unique_note_path(notes_dir, date_str)

    campaign_line = f"campaign: {campaign}\n" if campaign else ""
    campaign_tag = f"  - {campaign}\n" if campaign else ""

    content = (
        "---\n"
        f"date: {datetime_str}\n"
        f"{campaign_line}"
        "tags:\n"
        "  - session-notes\n"
        "  - ttrpg\n"
        "  - needs-summary\n"
        f"{campaign_tag}"
        "---\n\n"
        f"> [!warning] Summarisation failed\n"
        f"> {error}\n"
        "> This note contains the raw transcript only. "
        "Re-run `/watch` or summarise manually.\n\n"
        "## Raw Transcript\n\n"
        f"{transcript}\n"
    )

    note_path.write_text(content, encoding="utf-8")
    logger.warning("Saved fallback transcript note to %s", note_path)
    return note_path

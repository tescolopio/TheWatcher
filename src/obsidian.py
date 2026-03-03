"""Write session summary Markdown notes directly into an Obsidian vault.

Notes are saved under ``<OBSIDIAN_VAULT_PATH>/<OBSIDIAN_NOTES_FOLDER>/`` as
dated Markdown files with YAML front-matter.  If a note for today already
exists a numeric suffix is appended to avoid overwriting.
"""

import logging
import os
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


def _get_notes_dir() -> Path:
    """Resolve and create the notes directory inside the Obsidian vault.

    Returns:
        Path to the notes subdirectory.

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


def save_to_obsidian(summary_markdown: str) -> Path:
    """Write *summary_markdown* as a new note in the configured Obsidian vault.

    The note is prefixed with YAML front-matter containing the creation date
    and relevant tags so that Obsidian can index it immediately.

    Args:
        summary_markdown: Markdown text produced by the summariser.

    Returns:
        Absolute path of the newly created note file.
    """
    notes_dir = _get_notes_dir()
    now = datetime.now()
    date_str = now.strftime("%Y-%m-%d")
    datetime_str = now.strftime("%Y-%m-%d %H:%M")

    note_path = _unique_note_path(notes_dir, date_str)

    content = (
        "---\n"
        f"date: {datetime_str}\n"
        "tags:\n"
        "  - session-notes\n"
        "  - ttrpg\n"
        "---\n\n"
        f"{summary_markdown}\n"
    )

    note_path.write_text(content, encoding="utf-8")
    logger.info("Saved session note to %s", note_path)
    return note_path

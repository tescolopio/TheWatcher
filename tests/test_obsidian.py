"""Tests for src/obsidian.py – Obsidian vault note writer."""

from pathlib import Path
from unittest.mock import patch

import pytest

from src.obsidian import _get_notes_dir, _unique_note_path, save_fallback_note, save_to_obsidian


# ── _get_notes_dir ────────────────────────────────────────────────────────────


def test_get_notes_dir_raises_without_vault(monkeypatch):
    """ValueError is raised when OBSIDIAN_VAULT_PATH is not configured."""
    monkeypatch.delenv("OBSIDIAN_VAULT_PATH", raising=False)
    with pytest.raises(ValueError, match="OBSIDIAN_VAULT_PATH"):
        _get_notes_dir()


def test_get_notes_dir_creates_subdirectory(tmp_path, monkeypatch):
    """The notes sub-folder is created automatically."""
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(tmp_path))
    monkeypatch.setenv("OBSIDIAN_NOTES_FOLDER", "My Notes")
    notes_dir = _get_notes_dir()
    assert notes_dir == tmp_path / "My Notes"
    assert notes_dir.is_dir()


def test_get_notes_dir_default_folder(tmp_path, monkeypatch):
    """Default notes folder name is 'Session Notes'."""
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(tmp_path))
    monkeypatch.delenv("OBSIDIAN_NOTES_FOLDER", raising=False)
    notes_dir = _get_notes_dir()
    assert notes_dir.name == "Session Notes"


# ── _unique_note_path ─────────────────────────────────────────────────────────


def test_unique_path_no_collision(tmp_path):
    """Returns the base filename when no collision exists."""
    path = _unique_note_path(tmp_path, "2024-01-01")
    assert path == tmp_path / "Session - 2024-01-01.md"


def test_unique_path_single_collision(tmp_path):
    """Appends (2) when the base filename already exists."""
    (tmp_path / "Session - 2024-01-01.md").write_text("")
    path = _unique_note_path(tmp_path, "2024-01-01")
    assert path == tmp_path / "Session - 2024-01-01 (2).md"


def test_unique_path_multiple_collisions(tmp_path):
    """Increments counter until a free filename is found."""
    (tmp_path / "Session - 2024-01-01.md").write_text("")
    (tmp_path / "Session - 2024-01-01 (2).md").write_text("")
    (tmp_path / "Session - 2024-01-01 (3).md").write_text("")
    path = _unique_note_path(tmp_path, "2024-01-01")
    assert path == tmp_path / "Session - 2024-01-01 (4).md"


# ── save_to_obsidian ──────────────────────────────────────────────────────────


def test_save_to_obsidian_creates_file(tmp_path, monkeypatch):
    """A Markdown file is created and its path is returned."""
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(tmp_path))
    monkeypatch.setenv("OBSIDIAN_NOTES_FOLDER", "Notes")

    path = save_to_obsidian("## Summary\nGreat session.")

    assert path.exists()
    assert path.suffix == ".md"


def test_save_to_obsidian_yaml_frontmatter(tmp_path, monkeypatch):
    """The note starts with YAML front-matter containing date and tags."""
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(tmp_path))

    path = save_to_obsidian("## Overview\nHello.")
    content = path.read_text(encoding="utf-8")

    assert content.startswith("---\n")
    assert "date:" in content
    assert "session-notes" in content
    assert "ttrpg" in content
    assert "---" in content


def test_save_to_obsidian_includes_summary(tmp_path, monkeypatch):
    """The summary markdown text is present in the written file."""
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(tmp_path))

    summary = "## Session Overview\nThe heroes defeated the lich."
    path = save_to_obsidian(summary)
    content = path.read_text(encoding="utf-8")

    assert summary in content


def test_save_to_obsidian_no_overwrite(tmp_path, monkeypatch):
    """Two consecutive saves on the same day produce different files."""
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(tmp_path))

    path1 = save_to_obsidian("First session.")
    path2 = save_to_obsidian("Second session.")

    assert path1 != path2
    assert path1.exists()
    assert path2.exists()


def test_save_to_obsidian_raises_without_vault(monkeypatch):
    """ValueError propagates when the vault path is not configured."""
    monkeypatch.delenv("OBSIDIAN_VAULT_PATH", raising=False)
    with pytest.raises(ValueError, match="OBSIDIAN_VAULT_PATH"):
        save_to_obsidian("summary")


# ── _get_notes_dir – campaign sub-folder ──────────────────────────────────────


def test_get_notes_dir_creates_campaign_subfolder(tmp_path, monkeypatch):
    """When campaign is provided a subdirectory is created inside the notes folder."""
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(tmp_path))
    monkeypatch.setenv("OBSIDIAN_NOTES_FOLDER", "Session Notes")

    notes_dir = _get_notes_dir(campaign="Dragons of the North")

    assert notes_dir == tmp_path / "Session Notes" / "Dragons of the North"
    assert notes_dir.is_dir()


def test_get_notes_dir_without_campaign_uses_base(tmp_path, monkeypatch):
    """Without a campaign the notes land directly in the notes folder."""
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(tmp_path))
    monkeypatch.setenv("OBSIDIAN_NOTES_FOLDER", "Session Notes")

    notes_dir = _get_notes_dir()

    assert notes_dir == tmp_path / "Session Notes"


# ── save_to_obsidian – campaign + characters ──────────────────────────────────


def test_save_to_obsidian_campaign_creates_subfolder(tmp_path, monkeypatch):
    """With campaign provided the note is saved in a campaign sub-folder."""
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(tmp_path))
    monkeypatch.setenv("OBSIDIAN_NOTES_FOLDER", "Notes")

    path = save_to_obsidian("## Summary\nHello.", campaign="Dragons")

    # Parent directory must include the campaign name
    assert "Dragons" in str(path.parent)
    assert path.exists()


def test_save_to_obsidian_campaign_in_frontmatter(tmp_path, monkeypatch):
    """The campaign name appears in the YAML front-matter."""
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(tmp_path))

    path = save_to_obsidian("## Summary", campaign="Forgotten Realms")
    content = path.read_text(encoding="utf-8")

    assert "campaign: Forgotten Realms" in content


def test_save_to_obsidian_characters_in_frontmatter(tmp_path, monkeypatch):
    """Character names appear as a YAML list in the front-matter."""
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(tmp_path))

    path = save_to_obsidian("## Summary", characters=["Aragorn", "Legolas", "Gimli"])
    content = path.read_text(encoding="utf-8")

    assert "characters:" in content
    assert "Aragorn" in content
    assert "Legolas" in content
    assert "Gimli" in content


def test_save_to_obsidian_no_characters_no_field(tmp_path, monkeypatch):
    """Without characters the 'characters:' field is absent from the front-matter."""
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(tmp_path))

    path = save_to_obsidian("## Summary")
    content = path.read_text(encoding="utf-8")

    assert "characters:" not in content


# ── save_fallback_note ────────────────────────────────────────────────────────


def test_save_fallback_note_creates_file(tmp_path, monkeypatch):
    """save_fallback_note creates a Markdown file and returns its path."""
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(tmp_path))

    path = save_fallback_note("Raw transcript here.", "Ollama timeout")

    assert path.exists()
    assert path.suffix == ".md"


def test_save_fallback_note_contains_transcript(tmp_path, monkeypatch):
    """The raw transcript text is present in the fallback note body."""
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(tmp_path))

    path = save_fallback_note("The heroes rode west.", "Connection refused")
    content = path.read_text(encoding="utf-8")

    assert "The heroes rode west." in content


def test_save_fallback_note_has_needs_summary_tag(tmp_path, monkeypatch):
    """The note is tagged 'needs-summary' in its YAML front-matter."""
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(tmp_path))

    path = save_fallback_note("transcript", "error msg")
    content = path.read_text(encoding="utf-8")

    assert "needs-summary" in content


def test_save_fallback_note_contains_error(tmp_path, monkeypatch):
    """The error message appears in the warning callout block."""
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(tmp_path))

    path = save_fallback_note("transcript", "Connection timed out after 30s")
    content = path.read_text(encoding="utf-8")

    assert "Connection timed out after 30s" in content


def test_save_fallback_note_campaign_subfolder(tmp_path, monkeypatch):
    """With campaign provided the fallback note lands in the campaign sub-folder."""
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(tmp_path))

    path = save_fallback_note("transcript", "error", campaign="Dragon Quest")

    assert "Dragon Quest" in str(path.parent)
    assert path.exists()

"""Tests for src/obsidian.py – Obsidian vault note writer."""

from pathlib import Path
from unittest.mock import patch

import pytest

from src.obsidian import _get_notes_dir, _unique_note_path, save_to_obsidian


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

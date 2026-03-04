"""Tests for src/database.py – SQLite persistence layer."""

import os
import sqlite3
from pathlib import Path

import pytest

from src.database import (
    SessionStatus,
    create_session,
    delete_character,
    delete_config,
    get_active_recording_sessions,
    get_all_characters,
    get_all_config,
    get_character,
    get_config,
    get_guild_sessions,
    get_session,
    init_db,
    set_character,
    set_config,
    update_session,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _isolated_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Point the module at a fresh temp-dir database for every test."""
    db = tmp_path / "test_thewatcher.db"
    monkeypatch.setenv("THEWATCHER_DB", str(db))
    init_db()


# ── init_db ───────────────────────────────────────────────────────────────────


def test_init_db_creates_tables(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """init_db creates all three expected tables."""
    db_path = tmp_path / "fresh.db"
    monkeypatch.setenv("THEWATCHER_DB", str(db_path))
    init_db()

    conn = sqlite3.connect(str(db_path))
    cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = {row[0] for row in cursor.fetchall()}
    conn.close()

    assert "sessions" in tables
    assert "guild_config" in tables
    assert "characters" in tables


def test_init_db_is_idempotent() -> None:
    """Calling init_db twice does not raise or corrupt the schema."""
    init_db()
    init_db()  # second call is a no-op


# ── Session CRUD ──────────────────────────────────────────────────────────────


def test_create_session_returns_id() -> None:
    """create_session returns a non-empty string session ID."""
    sid = create_session(guild_id=1)
    assert isinstance(sid, str)
    assert len(sid) > 0


def test_create_session_stores_recording_status() -> None:
    """New sessions start with RECORDING status."""
    sid = create_session(guild_id=1)
    row = get_session(sid)
    assert row is not None
    assert row["status"] == SessionStatus.RECORDING


def test_create_session_stores_campaign() -> None:
    """Campaign name is persisted when provided."""
    sid = create_session(guild_id=1, campaign="Dragons of the North")
    row = get_session(sid)
    assert row is not None
    assert row["campaign"] == "Dragons of the North"


def test_update_session_status() -> None:
    """update_session changes the status field."""
    sid = create_session(guild_id=1)
    update_session(sid, status=SessionStatus.DONE)
    row = get_session(sid)
    assert row is not None
    assert row["status"] == SessionStatus.DONE


def test_update_session_multiple_fields() -> None:
    """Multiple keyword arguments are updated in one call."""
    sid = create_session(guild_id=1)
    update_session(sid, status=SessionStatus.PROCESSING, wav_path="/tmp/test.wav")
    row = get_session(sid)
    assert row is not None
    assert row["status"] == SessionStatus.PROCESSING
    assert row["wav_path"] == "/tmp/test.wav"


def test_update_session_error_message() -> None:
    """error_message is persisted on FAILED status."""
    sid = create_session(guild_id=1)
    update_session(sid, status=SessionStatus.FAILED, error_message="disk full")
    row = get_session(sid)
    assert row is not None
    assert row["error_message"] == "disk full"


def test_get_session_unknown_returns_none() -> None:
    """get_session returns None for an unknown ID."""
    row = get_session("nonexistent-id")
    assert row is None


def test_get_guild_sessions_returns_list() -> None:
    """get_guild_sessions returns all sessions for a guild."""
    gid = 42
    s1 = create_session(guild_id=gid)
    s2 = create_session(guild_id=gid)
    s3 = create_session(guild_id=999)  # different guild

    rows = get_guild_sessions(gid)
    ids = [r["id"] for r in rows]
    assert s1 in ids
    assert s2 in ids
    assert s3 not in ids


def test_get_guild_sessions_limit() -> None:
    """limit parameter caps the number of returned rows."""
    gid = 43
    for _ in range(5):
        create_session(guild_id=gid)
    rows = get_guild_sessions(gid, limit=3)
    assert len(rows) <= 3


def test_get_active_recording_sessions() -> None:
    """get_active_recording_sessions returns only RECORDING-status rows."""
    s_rec = create_session(guild_id=1)
    s_done = create_session(guild_id=1)
    update_session(s_done, status=SessionStatus.DONE)

    active = get_active_recording_sessions()
    active_ids = [r["id"] for r in active]
    assert s_rec in active_ids
    assert s_done not in active_ids


# ── Guild config ──────────────────────────────────────────────────────────────


def test_set_and_get_config() -> None:
    """Config values can be set and retrieved."""
    set_config(guild_id=1, key="campaign", value="Test Campaign")
    assert get_config(guild_id=1, key="campaign") == "Test Campaign"


def test_get_config_missing_returns_none() -> None:
    """get_config returns None when no value is stored."""
    assert get_config(guild_id=99, key="missing_key") is None


def test_delete_config() -> None:
    """delete_config removes a stored value."""
    set_config(guild_id=1, key="campaign", value="Test Campaign")
    delete_config(guild_id=1, key="campaign")
    assert get_config(guild_id=1, key="campaign") is None


def test_delete_config_nonexistent_is_noop() -> None:
    """Deleting a non-existent key does not raise."""
    delete_config(guild_id=1, key="no_such_key")  # must not raise


def test_get_all_config_returns_dict() -> None:
    """get_all_config returns all stored key-value pairs for the guild."""
    set_config(guild_id=5, key="campaign", value="Forgotten Realms")
    set_config(guild_id=5, key="ollama_model", value="llama3")
    cfg = get_all_config(guild_id=5)
    assert cfg["campaign"] == "Forgotten Realms"
    assert cfg["ollama_model"] == "llama3"


def test_config_is_guild_isolated() -> None:
    """Config values from different guilds do not bleed into each other."""
    set_config(guild_id=1, key="campaign", value="Guild 1 Campaign")
    set_config(guild_id=2, key="campaign", value="Guild 2 Campaign")
    assert get_config(guild_id=1, key="campaign") == "Guild 1 Campaign"
    assert get_config(guild_id=2, key="campaign") == "Guild 2 Campaign"


def test_set_config_upserts() -> None:
    """set_config overwrites the existing value (upsert behaviour)."""
    set_config(guild_id=1, key="campaign", value="Old")
    set_config(guild_id=1, key="campaign", value="New")
    assert get_config(guild_id=1, key="campaign") == "New"


# ── Character registry ────────────────────────────────────────────────────────


def test_set_and_get_character() -> None:
    """Character names can be set and retrieved by (guild_id, user_id)."""
    set_character(guild_id=1, user_id=100, name="Aragorn")
    assert get_character(guild_id=1, user_id=100) == "Aragorn"


def test_get_character_missing_returns_none() -> None:
    """get_character returns None when no entry exists."""
    assert get_character(guild_id=1, user_id=9999) is None


def test_delete_character() -> None:
    """delete_character removes the entry."""
    set_character(guild_id=1, user_id=100, name="Aragorn")
    delete_character(guild_id=1, user_id=100)
    assert get_character(guild_id=1, user_id=100) is None


def test_delete_character_nonexistent_is_noop() -> None:
    """Deleting a non-existent character does not raise."""
    delete_character(guild_id=1, user_id=999)  # must not raise


def test_get_all_characters_returns_dict() -> None:
    """get_all_characters returns all registrations for the guild as {user_id: name}."""
    set_character(guild_id=1, user_id=10, name="Legolas")
    set_character(guild_id=1, user_id=20, name="Gimli")
    chars = get_all_characters(guild_id=1)
    assert chars[10] == "Legolas"
    assert chars[20] == "Gimli"


def test_characters_are_guild_isolated() -> None:
    """Characters registered for one guild are not visible in another guild."""
    set_character(guild_id=1, user_id=1, name="Frodo")
    set_character(guild_id=2, user_id=1, name="Sauron")
    assert get_character(guild_id=1, user_id=1) == "Frodo"
    assert get_character(guild_id=2, user_id=1) == "Sauron"


def test_set_character_upserts() -> None:
    """set_character replaces the existing name (upsert behaviour)."""
    set_character(guild_id=1, user_id=1, name="Bilbo")
    set_character(guild_id=1, user_id=1, name="Frodo")
    assert get_character(guild_id=1, user_id=1) == "Frodo"

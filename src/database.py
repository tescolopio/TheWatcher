"""Lightweight SQLite persistence layer for RPG Watcher.

Three tables:
- ``sessions``      – one row per recording session; status flows through
                      RECORDING → PROCESSING → DONE | FAILED.
- ``guild_config``  – per-guild key/value overrides (set via ``/config``).
- ``characters``    – per-guild-per-user character name registry (``/character``).

The database file location defaults to ``rpgwatcher.db`` in the working
directory; override with ``RPGWATCHER_DB`` env var.
"""

import logging
import os
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Generator, Optional

logger = logging.getLogger(__name__)

# ── Database path ─────────────────────────────────────────────────────────────


def _db_path() -> Path:
    """Return the resolved path for the SQLite database file."""
    path = Path(os.getenv("RPGWATCHER_DB", "rpgwatcher.db"))
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


@contextmanager
def _connect() -> Generator[sqlite3.Connection, None, None]:
    """Yield a WAL-mode SQLite connection with automatic commit/rollback."""
    conn = sqlite3.connect(str(_db_path()), timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ── Schema ────────────────────────────────────────────────────────────────────


class SessionStatus(str, Enum):
    """Lifecycle states for a recording session."""

    RECORDING = "recording"
    PROCESSING = "processing"
    DONE = "done"
    FAILED = "failed"


def init_db() -> None:
    """Create all tables if they do not already exist (idempotent)."""
    with _connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                id              TEXT PRIMARY KEY,
                guild_id        INTEGER NOT NULL,
                channel_id      INTEGER,
                voice_channel   TEXT,
                wav_path        TEXT,
                status          TEXT NOT NULL DEFAULT 'recording',
                started_at      TEXT NOT NULL,
                ended_at        TEXT,
                transcript      TEXT,
                summary         TEXT,
                note_path       TEXT,
                error_message   TEXT,
                campaign        TEXT,
                correlation_id  TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS guild_config (
                guild_id        INTEGER NOT NULL,
                key             TEXT NOT NULL,
                value           TEXT NOT NULL,
                PRIMARY KEY (guild_id, key)
            );

            CREATE TABLE IF NOT EXISTS characters (
                guild_id        INTEGER NOT NULL,
                user_id         INTEGER NOT NULL,
                character_name  TEXT NOT NULL,
                PRIMARY KEY (guild_id, user_id)
            );
            """
        )
    logger.debug("Database initialised at %s", _db_path())


# ── Session CRUD ──────────────────────────────────────────────────────────────


def create_session(
    guild_id: int,
    channel_id: Optional[int] = None,
    voice_channel: Optional[str] = None,
    campaign: Optional[str] = None,
) -> str:
    """Insert a new session in RECORDING status and return its UUID."""
    session_id = str(uuid.uuid4())
    correlation_id = str(uuid.uuid4())[:8]
    now = datetime.utcnow().isoformat()
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO sessions
                (id, guild_id, channel_id, voice_channel, status,
                 started_at, campaign, correlation_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                session_id,
                guild_id,
                channel_id,
                voice_channel,
                SessionStatus.RECORDING,
                now,
                campaign,
                correlation_id,
            ),
        )
    logger.debug("Created session %s for guild %d [corr:%s]", session_id, guild_id, correlation_id)
    return session_id


def update_session(session_id: str, **kwargs: object) -> None:
    """Update arbitrary columns on a session row.

    Only whitelisted column names are accepted to prevent SQL injection.
    """
    allowed = {
        "status",
        "ended_at",
        "wav_path",
        "transcript",
        "summary",
        "note_path",
        "error_message",
        "campaign",
    }
    cols = [k for k in kwargs if k in allowed]
    if not cols:
        return
    placeholders = ", ".join(f"{c} = ?" for c in cols)
    values: list[object] = [kwargs[c] for c in cols] + [session_id]
    with _connect() as conn:
        conn.execute(
            f"UPDATE sessions SET {placeholders} WHERE id = ?",  # noqa: S608
            values,
        )


def get_session(session_id: str) -> Optional[sqlite3.Row]:
    """Fetch a single session row by ID, or None if not found."""
    with _connect() as conn:
        return conn.execute(
            "SELECT * FROM sessions WHERE id = ?", (session_id,)
        ).fetchone()


def get_guild_sessions(guild_id: int, limit: int = 10) -> list[sqlite3.Row]:
    """Return the most recent *limit* sessions for a guild."""
    with _connect() as conn:
        return conn.execute(
            "SELECT * FROM sessions WHERE guild_id = ? ORDER BY started_at DESC LIMIT ?",
            (guild_id, limit),
        ).fetchall()


def get_active_recording_sessions() -> list[sqlite3.Row]:
    """Return all sessions still in RECORDING status (used to detect restarts)."""
    with _connect() as conn:
        return conn.execute(
            "SELECT * FROM sessions WHERE status = ?",
            (SessionStatus.RECORDING,),
        ).fetchall()


# ── Guild config ──────────────────────────────────────────────────────────────


def get_config(guild_id: int, key: str, default: Optional[str] = None) -> Optional[str]:
    """Return a per-guild config value, or *default* if absent."""
    with _connect() as conn:
        row = conn.execute(
            "SELECT value FROM guild_config WHERE guild_id = ? AND key = ?",
            (guild_id, key),
        ).fetchone()
    return str(row["value"]) if row else default


def set_config(guild_id: int, key: str, value: str) -> None:
    """Upsert a per-guild config value."""
    with _connect() as conn:
        conn.execute(
            "INSERT INTO guild_config (guild_id, key, value) VALUES (?, ?, ?)"
            "  ON CONFLICT(guild_id, key) DO UPDATE SET value = excluded.value",
            (guild_id, key, value),
        )


def delete_config(guild_id: int, key: str) -> None:
    """Remove a specific per-guild config entry."""
    with _connect() as conn:
        conn.execute(
            "DELETE FROM guild_config WHERE guild_id = ? AND key = ?",
            (guild_id, key),
        )


def get_all_config(guild_id: int) -> dict[str, str]:
    """Return all config entries for a guild as ``{key: value}``."""
    with _connect() as conn:
        rows = conn.execute(
            "SELECT key, value FROM guild_config WHERE guild_id = ?",
            (guild_id,),
        ).fetchall()
    return {row["key"]: row["value"] for row in rows}


# ── Character registry ────────────────────────────────────────────────────────


def set_character(guild_id: int, user_id: int, character_name: str) -> None:
    """Register or update a player's in-game character name."""
    with _connect() as conn:
        conn.execute(
            "INSERT INTO characters (guild_id, user_id, character_name) VALUES (?, ?, ?)"
            "  ON CONFLICT(guild_id, user_id) DO UPDATE"
            "  SET character_name = excluded.character_name",
            (guild_id, user_id, character_name),
        )


def get_character(guild_id: int, user_id: int) -> Optional[str]:
    """Return a player's registered character name, or None if unregistered."""
    with _connect() as conn:
        row = conn.execute(
            "SELECT character_name FROM characters WHERE guild_id = ? AND user_id = ?",
            (guild_id, user_id),
        ).fetchone()
    return str(row["character_name"]) if row else None


def get_all_characters(guild_id: int) -> dict[int, str]:
    """Return all registered characters for a guild as ``{user_id: name}``."""
    with _connect() as conn:
        rows = conn.execute(
            "SELECT user_id, character_name FROM characters WHERE guild_id = ?",
            (guild_id,),
        ).fetchall()
    return {int(row["user_id"]): str(row["character_name"]) for row in rows}


def delete_character(guild_id: int, user_id: int) -> None:
    """Remove a player's character registration."""
    with _connect() as conn:
        conn.execute(
            "DELETE FROM characters WHERE guild_id = ? AND user_id = ?",
            (guild_id, user_id),
        )

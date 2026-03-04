# Configuration Reference

All configuration is done through environment variables loaded from a `.env` file in the project root (via `python-dotenv`).  Copy `.env.example` to `.env` and fill in your values before running the bot.

---

## Required Variables

These must be set; the bot will not start successfully without them.

### `DISCORD_BOT_TOKEN`

| | |
|--|--|
| **Type** | string |
| **Default** | *(none — required)* |
| **Example** | `DISCORD_BOT_TOKEN=MTIz...` |

The token for your Discord application bot.  Obtain it from the [Discord Developer Portal](https://discord.com/developers/applications) under **Bot → Token**.

---

### `OBSIDIAN_VAULT_PATH`

| | |
|--|--|
| **Type** | absolute filesystem path |
| **Default** | *(none — required)* |
| **Example** | `OBSIDIAN_VAULT_PATH=/home/alice/Documents/MyVault` |

Absolute path to the root directory of your Obsidian vault.  The bot creates the notes sub-folder inside this directory automatically.

---

## Optional Variables

### Obsidian

#### `OBSIDIAN_NOTES_FOLDER`

| | |
|--|--|
| **Type** | string (relative path within the vault) |
| **Default** | `Session Notes` |
| **Example** | `OBSIDIAN_NOTES_FOLDER=TTRPG/Sessions` |

Sub-folder (relative to `OBSIDIAN_VAULT_PATH`) where session notes are saved.  Intermediate directories are created automatically.

---

### Recording

#### `RECORDINGS_DIR`

| | |
|--|--|
| **Type** | absolute filesystem path |
| **Default** | `/tmp/thewatcher_recordings` |
| **Example** | `RECORDINGS_DIR=/var/data/thewatcher` |

Directory where WAV files are written after a `/unwatch`.  The bot creates this directory if it does not exist.

> **Note:** On Linux, `/tmp` is cleared on reboot.  Point this at a persistent location if you want to keep raw audio for debugging.

---

### Transcription

#### `WHISPER_CPP_PATH`

| | |
|--|--|
| **Type** | absolute filesystem path |
| **Default** | *(unset — Python backend used)* |
| **Example** | `WHISPER_CPP_PATH=/usr/local/bin/whisper-cpp/main` |

Path to the compiled `main` binary from [whisper.cpp](https://github.com/ggerganov/whisper.cpp).  When this is set and the file is executable, the bot uses `whisper.cpp` instead of the `openai-whisper` Python package.

The bot looks for GGML model files at `<WHISPER_CPP_PATH>/../models/ggml-<WHISPER_MODEL>.bin`.

#### `WHISPER_MODEL`

| | |
|--|--|
| **Type** | string |
| **Default** | `base` |
| **Allowed values** | `tiny`, `base`, `small`, `medium`, `large`, `large-v2`, `large-v3` |
| **Example** | `WHISPER_MODEL=small` |

Whisper model size.  Larger models produce better transcripts but require more RAM and time.

| Model | VRAM / RAM | Relative speed |
|-------|-----------|----------------|
| `tiny` | ~1 GB | fastest |
| `base` | ~1 GB | fast |
| `small` | ~2 GB | moderate |
| `medium` | ~5 GB | slow |
| `large` | ~10 GB | slowest |

---

### Summarisation (Ollama)

#### `OLLAMA_BASE_URL`

| | |
|--|--|
| **Type** | URL |
| **Default** | `http://localhost:11434` |
| **Example** | `OLLAMA_BASE_URL=http://192.168.1.50:11434` |

Base URL of the Ollama HTTP API.  Change this if Ollama is running on a different host or port.

#### `OLLAMA_MODEL`

| | |
|--|--|
| **Type** | string |
| **Default** | `mistral` |
| **Example** | `OLLAMA_MODEL=llama3` |

Name of the locally pulled Ollama model to use for summarisation.  The model must already be available (`ollama pull <model>`).

Recommended models for TTRPG summarisation:

| Model | Context window | Notes |
|-------|---------------|-------|
| `mistral` | 8 k | Fast, good quality — recommended default |
| `llama3` | 8 k | Strong instruction following |
| `gemma2` | 8 k | Good balance of speed and quality |
| `mixtral` | 32 k | Better for very long sessions |

---

## Complete `.env.example`

```dotenv
# ── Required ──────────────────────────────────────────────────────────────────

# Your Discord bot token (from https://discord.com/developers/applications)
DISCORD_BOT_TOKEN=your_token_here

# Absolute path to your Obsidian vault root directory
OBSIDIAN_VAULT_PATH=/absolute/path/to/your/vault

# ── Obsidian ──────────────────────────────────────────────────────────────────

# Sub-folder inside the vault where session notes are created (default: "Session Notes")
# OBSIDIAN_NOTES_FOLDER=Session Notes

# ── Recording ─────────────────────────────────────────────────────────────────

# Directory for temporary WAV files (default: /tmp/thewatcher_recordings)
# RECORDINGS_DIR=/tmp/thewatcher_recordings

# ── Transcription ─────────────────────────────────────────────────────────────

# Path to the whisper.cpp main binary (leave unset to use the Python package instead)
# WHISPER_CPP_PATH=/usr/local/bin/whisper-cpp/main

# Whisper model size: tiny | base | small | medium | large (default: base)
# WHISPER_MODEL=base

# ── Summarisation ─────────────────────────────────────────────────────────────

# Ollama server URL (default: http://localhost:11434)
# OLLAMA_BASE_URL=http://localhost:11434

# Ollama model name — must be pulled first with `ollama pull <model>` (default: mistral)
# OLLAMA_MODEL=mistral
```

---

## Precedence

1. Actual environment variables in the shell take highest precedence.
2. Variables defined in `.env` are loaded by `python-dotenv` at startup and only applied if not already set in the environment.

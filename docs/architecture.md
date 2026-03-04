# Architecture

TheWatcher is a single-process Python application.  This document describes the data flow, module responsibilities, and extension points so contributors can understand the codebase quickly.

---

## High-Level Data Flow

```
Discord Voice Channel
        │
        │  48 kHz, 16-bit stereo PCM (per user)
        ▼
┌──────────────────┐
│  RecordingSink   │  src/recorder.py
│  (PCMSink)       │  Collects raw per-user PCM frames in memory
└────────┬─────────┘
         │  per-user BytesIO buffers
         ▼
┌──────────────────┐
│  merge_audio_data│  src/recorder.py
│                  │  Zero-pads, sums, and clamps 16-bit samples;
│                  │  writes a stereo WAV container
└────────┬─────────┘
         │  WAV file on disk  (RECORDINGS_DIR)
         ▼
┌──────────────────┐
│   transcribe()   │  src/transcriber.py
│                  │  Routes to whisper.cpp subprocess  ← WHISPER_CPP_PATH set
│                  │        or openai-whisper Python pkg ← fallback
└────────┬─────────┘
         │  plain-text transcript
         ▼
┌──────────────────┐
│   summarize()    │  src/summarizer.py
│                  │  Sends transcript to local Ollama instance;
│                  │  structured Markdown returned
└────────┬─────────┘
         │  Markdown summary
         ▼
┌──────────────────┐
│ save_to_obsidian │  src/obsidian.py
│                  │  Prepends YAML front-matter;
│                  │  writes dated .md file to vault
└────────┬─────────┘
         │  note path
         ▼
    Discord channel
    (status messages + summary preview)
```

---

## Module Reference

### `src/bot.py`

Entry point.  Instantiates the `discord.ext.commands.Bot`, registers two slash commands, and wires the pipeline callback.

| Symbol | Purpose |
|--------|---------|
| `bot` | Global `commands.Bot` instance |
| `_active_recordings` | `dict[guild_id, VoiceClient]` — one entry per actively recording guild |
| `watch()` | Slash command: join voice channel, start `RecordingSink` |
| `unwatch()` | Slash command: stop sink, fire `_on_recording_finished` |
| `_on_recording_finished()` | Async pipeline callback (runs stages via `asyncio.to_thread`) |

All blocking I/O (disk writes, model inference) is offloaded with `asyncio.to_thread` to keep the Discord event loop responsive.

---

### `src/recorder.py`

Handles audio capture and WAV serialisation.

| Symbol | Purpose |
|--------|---------|
| `RecordingSink` | Thin `PCMSink` subclass; no custom logic — provides a distinct type for type annotations |
| `merge_audio_data(audio_data)` | Mixes per-user PCM tracks into a single stereo WAV |
| `finish_recording(sink)` | Calls `merge_audio_data`, writes WAV to `RECORDINGS_DIR`, returns the path |
| `_get_recordings_dir()` | Resolves and creates the recordings directory |

**PCM constants** (matching Discord Opus decoder output):

| Constant | Value |
|----------|-------|
| `_SAMPLE_RATE` | 48 000 Hz |
| `_CHANNELS` | 2 (stereo) |
| `_SAMPLE_WIDTH` | 2 bytes (16-bit signed LE) |

---

### `src/transcriber.py`

Selects and invokes the appropriate Whisper backend.

| Symbol | Purpose |
|--------|---------|
| `transcribe(audio_path)` | Public entry point — selects backend automatically |
| `_transcribe_with_whisper_cpp(audio_path)` | Invokes `WHISPER_CPP_PATH` binary via `subprocess.run` |
| `_transcribe_with_python_whisper(audio_path)` | Uses `whisper.load_model` + `model.transcribe` |

**Backend selection logic:**

```
WHISPER_CPP_PATH set and file is executable?
  → whisper.cpp subprocess
  else
  → openai-whisper Python package
```

**Env vars consumed:**

| Variable | Default | Effect |
|----------|---------|--------|
| `WHISPER_CPP_PATH` | *(unset)* | Path to the `main` whisper.cpp binary |
| `WHISPER_MODEL` | `base` | Model name (e.g. `tiny`, `small`, `medium`, `large`) |

---

### `src/summarizer.py`

Wraps the Ollama Python client.

| Symbol | Purpose |
|--------|---------|
| `summarize(transcript)` | Sends `_SYSTEM_PROMPT` + transcript to Ollama; returns Markdown |
| `_SYSTEM_PROMPT` | Module-level constant defining the TTRPG note-taker persona and output structure |

**Required Ollama output sections:** Session Overview · Key Events · NPC Interactions · Player Decisions · Cliffhangers / Open Threads

**Env vars consumed:**

| Variable | Default | Effect |
|----------|---------|--------|
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama server URL |
| `OLLAMA_MODEL` | `mistral` | Model name (must be pulled locally) |

---

### `src/obsidian.py`

Writes Markdown notes into an Obsidian vault.

| Symbol | Purpose |
|--------|---------|
| `save_to_obsidian(summary_markdown)` | Public entry point |
| `_get_notes_dir()` | Resolves vault path and creates the notes sub-folder |
| `_unique_note_path(notes_dir, date_str)` | Returns a collision-free filename for today |

**Note filename format:** `Session - YYYY-MM-DD.md`  (or `Session - YYYY-MM-DD (2).md` on collision)

**YAML front-matter schema (current):**

```yaml
---
date: YYYY-MM-DD HH:MM
tags:
  - session-notes
  - ttrpg
---
```

**Env vars consumed:**

| Variable | Default | Effect |
|----------|---------|--------|
| `OBSIDIAN_VAULT_PATH` | *(required)* | Absolute path to the vault root |
| `OBSIDIAN_NOTES_FOLDER` | `Session Notes` | Sub-folder inside the vault |

---

## Concurrency Model

The bot runs a single `asyncio` event loop.  All three pipeline stages (`transcribe`, `summarize`, `save_to_obsidian`) are synchronous and CPU/IO-bound; they are dispatched to the default `ThreadPoolExecutor` via `asyncio.to_thread`.

Implications:
- Multiple guilds recording simultaneously will share the interpreter's thread pool.
- The Ollama call may block a pool thread for tens of seconds on slow hardware.
- No work is parallelised within a single session; stages run sequentially.

Future work (v0.3+): move to a dedicated worker thread or process pool for pipeline stages to bound latency.

---

## Environment Variables Quick Reference

See [configuration.md](configuration.md) for the full reference with types, defaults, and examples.

---

## Directory Layout

```
TheWatcher/
├── src/
│   ├── __init__.py
│   ├── bot.py          ← entry point, slash commands
│   ├── recorder.py     ← PCM capture and WAV serialisation
│   ├── transcriber.py  ← Whisper backend selection
│   ├── summarizer.py   ← Ollama LLM client
│   └── obsidian.py     ← vault note writer
├── tests/
│   ├── test_recorder.py
│   ├── test_transcriber.py
│   ├── test_summarizer.py
│   └── test_obsidian.py
├── docs/
│   ├── roadmap.md
│   ├── architecture.md ← this file
│   ├── configuration.md
│   └── contributing.md
├── requirements.txt
├── requirements-dev.txt
└── README.md
```

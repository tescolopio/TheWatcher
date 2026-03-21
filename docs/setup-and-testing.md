# Setup & Testing Guide

This guide walks you through getting RPG Watcher running and verifying every feature in a live Discord server.

---

## Part 1 — Discord Developer Setup

### 1.1 Create the Application

1. Go to <https://discord.com/developers/applications> and click **New Application**.
2. Give it a name (e.g. *RPG Watcher*) and click **Create**.

### 1.2 Configure the Bot

1. In the left sidebar select **Bot**.
2. Click **Reset Token**, copy the token, and store it somewhere safe — you'll need it in `.env`.
3. Under **Privileged Gateway Intents**, enable:
   - **Server Members Intent**
   - **Voice States Intent**
4. Click **Save Changes**.

### 1.3 Invite the Bot to Your Server

1. In the left sidebar select **OAuth2 → URL Generator**.
2. Under **Scopes** check: `bot`, `applications.commands`.
3. Under **Bot Permissions** check:
   - Connect
   - Speak
   - Use Voice Activity
   - Read Messages / View Channels
   - Send Messages
4. Copy the generated URL, open it in a browser, and select your server.

> **Note:** Slash commands can take up to 1 hour to appear in Discord after the bot first syncs them. If commands don't show up immediately, wait and try again — or kick/re-invite the bot.

---

## Part 2 — Local Deployment

### 2.1 Clone & Install

```bash
git clone https://github.com/tescolopio/rpgwatcher.git
cd rpgwatcher
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2.2 Configure `.env`

```bash
cp .env.example .env
```

Open `.env` and set the required values:

```dotenv
# Required
DISCORD_BOT_TOKEN=your_token_from_step_1.2
OBSIDIAN_VAULT_PATH=/absolute/path/to/your/vault

# Optional — shown with defaults
WHISPER_MODEL=base                        # tiny | base | small | medium | large
WHISPER_CPP_PATH=                         # leave empty to use openai-whisper
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=mistral
OBSIDIAN_NOTES_FOLDER=Session Notes
RECORDINGS_DIR=/tmp/rpgwatcher_recordings
MIN_FREE_DISK_MB=500
LOG_FORMAT=text                           # text | json
ALLOWED_ROLE_IDS=                         # comma-separated Discord role IDs, or leave empty
```

> **Obsidian vault path**: must be an absolute path to the directory that *contains* your vault (i.e. the folder you open in Obsidian). The bot writes notes to `<OBSIDIAN_VAULT_PATH>/<OBSIDIAN_NOTES_FOLDER>/Session - YYYY-MM-DD.md`.

### 2.3 Start Ollama

```bash
ollama serve &
ollama pull mistral      # ~4 GB — run once
```

You can verify Ollama is ready:

```bash
curl http://localhost:11434/api/tags
```

### 2.4 (Optional) Install whisper.cpp for Faster Transcription

```bash
git clone https://github.com/ggerganov/whisper.cpp.git
cd whisper.cpp
cmake -B build
cmake --build build --config Release
bash models/download-ggml-model.sh base
```

Then set in `.env`:

```dotenv
WHISPER_CPP_PATH=/absolute/path/to/whisper.cpp/build/bin/whisper-cli
WHISPER_MODEL=base
```

### 2.5 Run the Bot

```bash
python -m src.bot
```

Expected startup output:

```
2026-03-04 10:00:00 [INFO] __main__: Logged in as RPG Watcher#1234 (ID: 123456789)
2026-03-04 10:00:01 [INFO] __main__: Synced 8 slash command(s).
```

If you see `Failed to sync commands`, re-check that the `applications.commands` scope was included when inviting the bot.

---

## Part 3 — Docker Deployment (Alternative)

```bash
cp .env.example .env
# Set DISCORD_BOT_TOKEN and OBSIDIAN_VAULT_PATH in .env

docker compose up -d
docker compose exec ollama ollama pull mistral

# Confirm the bot is live
docker compose logs -f rpg-watcher
```

To stop everything: `docker compose down`  
To wipe all stored data (recordings, database, model weights): `docker compose down -v`

---

## Part 4 — Automated Tests

Run the full test suite before deploying or after any code change:

```bash
pip install -r requirements-dev.txt
pytest
```

To see verbose output and coverage:

```bash
pytest -v --tb=short
```

### What the tests cover

| Test file | What it exercises |
|---|---|
| `tests/test_bot.py` | All slash commands, pipeline stages, error paths, embed content |
| `tests/test_recorder.py` | PCM mixing, WAV file writing, per-speaker extraction |
| `tests/test_transcriber.py` | Backend selection, subprocess call for whisper.cpp, Python fallback |
| `tests/test_summarizer.py` | Ollama prompt construction and response parsing |
| `tests/test_obsidian.py` | Note file writing, YAML front-matter, fallback note |
| `tests/test_database.py` | Session CRUD, character registry, per-guild config |
| `tests/test_audio.py` | Audio utility functions |
| `tests/test_integration.py` | Full pipeline end-to-end with mocked I/O |

All tests run offline with mocked Discord and Ollama clients — no live credentials or services needed.

---

## Part 5 — Manual Discord Testing Checklist

Work through these steps in your server after the bot is running. Each step verifies a distinct feature.

### 5.1 Health Check

Run `/status` in any text channel (the response is ephemeral — only you see it).

**Expected:** An embed showing:
- Latency in ms
- Ollama connectivity (✅ if `ollama serve` is running, ❌ if not)
- Whisper backend (either `whisper.cpp` path or `openai-whisper` with model size)
- Vault path (or ❌ if `OBSIDIAN_VAULT_PATH` is not set)
- Free disk space vs threshold

If Ollama shows ❌, confirm it is running: `curl http://localhost:11434/api/tags`

---

### 5.2 Basic Recording → Full Pipeline

1. Join a voice channel in your server.
2. Run `/watch` in a text channel.
   - **Expected:** An embed saying "🎙️ Recording Started" with the voice channel name.
3. Speak for at least 10–15 seconds to give Whisper meaningful audio.
4. Run `/unwatch`.
   - **Expected:** An embed saying "⏹️ Recording Stopped" followed by a series of processing updates:
     - "🔄 Saving audio…"
     - "🗣️ Transcribing with Whisper…"
     - "🧠 Generating summary with Ollama…"
     - "✅ Session Summary Ready" — with a Markdown preview and an **Open in Obsidian** button (if vault is configured)
5. Open your Obsidian vault and confirm a note was created under `<OBSIDIAN_NOTES_FOLDER>/Session - YYYY-MM-DD.md` with YAML front-matter.

---

### 5.3 Session History

After completing step 5.2, run `/sessions`.

**Expected:** An ephemeral embed listing the session with:
- ✅ status
- Truncated session ID
- Timestamp
- Campaign name (if set)

---

### 5.4 Campaign Tagging

1. Run `/campaign set name:My Campaign`.
   - **Expected:** "📖 Campaign set to **My Campaign**."
2. Run `/watch`, speak briefly, then `/unwatch`.
   - **Expected:** The "Recording Started" embed shows "Campaign: **My Campaign**". The summary embed footer shows the campaign name. The saved note's YAML front-matter includes the campaign.
3. Run `/campaign clear`.
   - **Expected:** "📖 Campaign cleared."

---

### 5.5 Character Registry & Labelled Transcription

1. Run `/character set name:Aragorn` (each player who wants labelled segments does this).
2. Run `/character list` to confirm the mapping is saved.
   - **Expected:** Embed showing "**Aragorn** — YourDisplayName".
3. Run `/watch`, have the registered player(s) speak, then `/unwatch`.
   - **Expected:** The transcript is labelled with character names (e.g. `[Aragorn]: ...`)
4. Run `/character clear` to remove your registration.

---

### 5.6 Mic Check (Preview)

1. Join a voice channel.
2. Run `/preview`.
   - **Expected:** "🎙️ Recording Preview — Recording for 5 seconds…"
3. After 5 seconds, the bot automatically stops and posts a `preview.wav` file in the text channel.
4. Download and play the file to verify your mic is audible.

---

### 5.7 Admin Config Override

*Requires **Manage Server** permission.*

Run `/config key:ollama_model value:llama3` to switch the LLM model for this server without editing `.env`.

**Expected:** "⚙️ `ollama_model` set to **llama3**."

Valid keys: `ollama_model`, `notes_folder`, `campaign`, `silence_threshold_db`.

To reset to the global default: `/config key:ollama_model` (omit the value).

---

### 5.8 Error Path Verification

These steps confirm the bot handles failures gracefully.

| Test | How to trigger | Expected behaviour |
|---|---|---|
| `/watch` outside voice | Run command without joining a VC | Ephemeral: "You must be in a voice channel" |
| `/unwatch` with no recording | Run `/unwatch` without a prior `/watch` | Ephemeral: "No active recording found" |
| `/watch` twice | Run `/watch` twice without `/unwatch` | Second call: ephemeral "Already recording" |
| Ollama down | Stop `ollama serve`, then run a full session | ⚠️ "Summary Failed — Transcript Saved" embed; raw transcript saved as fallback note |
| Bad vault path | Set `OBSIDIAN_VAULT_PATH` to a non-existent directory | ⚠️ "Summary Ready — Obsidian Save Failed" embed; summary still shown |
| Low disk space | Set `MIN_FREE_DISK_MB` higher than available space | `/watch` rejected with "Not enough free disk space" |

---

## Part 6 — Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| Slash commands not visible | Commands not synced yet | Wait up to 1 hour; re-invite bot if persists |
| `Logged in` but no commands appear | Missing `applications.commands` scope | Re-invite the bot using the URL from step 1.3 |
| `/watch` fails: "Could not join voice channel" | Bot missing Connect/Speak permissions in that channel | Check channel-level permission overrides in Discord |
| `/unwatch` triggers no output | `finish_recording` or audio save error | Check bot logs for the exception |
| Transcription very slow | Using `openai-whisper` on CPU | Install `whisper.cpp` and set `WHISPER_CPP_PATH` |
| `Transcription failed: model not found` | Whisper model not downloaded | Run `ollama pull <model>` or download the GGML model |
| `Summarisation failed: connection refused` | Ollama not running | Run `ollama serve` |
| Notes not appearing in Obsidian | Wrong `OBSIDIAN_VAULT_PATH` | Confirm path is absolute and the directory exists |
| Bot joins but records silence | PyNaCl or ffmpeg missing | `pip install PyNaCl` and install ffmpeg |
| Docker: notes not appearing | Host vault path not bind-mounted | Verify `OBSIDIAN_VAULT_PATH` in `.env` is the *host* path; compose file mounts it to `/vault` |

---

## See Also

- [Local Deployment](deployment/local.md)
- [Docker Deployment](deployment/docker.md)
- [Configuration Reference](configuration.md)
- [Architecture](architecture.md)

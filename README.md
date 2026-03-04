# TheWatcher

![CI](https://github.com/tescolopio/TheWatcher/actions/workflows/ci.yml/badge.svg)

An open-source, **privacy-first** Discord bot that records your tabletop RPG voice
sessions, transcribes them **entirely on your own hardware**, and generates a
structured Markdown summary that lands directly in your Obsidian vault—no cloud
services, no subscriptions, no data leaves your machine.

```
Voice channel → py-cord PCMSink recording → Whisper (local) → Ollama (local) → Obsidian vault
```

---

## Features

| Feature | Detail |
|---|---|
| 🎙️ Voice recording | Joins any Discord voice channel on demand |
| 🗣️ Local transcription | [whisper.cpp](https://github.com/ggerganov/whisper.cpp) (fast, CPU-only) **or** [openai-whisper](https://github.com/openai/whisper) Python package |
| 🧠 Local summarisation | Any model served by [Ollama](https://ollama.com) (`mistral`, `llama3`, etc.) |
| 📓 Obsidian integration | Dated Markdown notes with YAML front-matter dropped straight into your vault |
| 🔒 100 % local | No audio, transcript, or summary ever leaves your machine |

---

## Requirements

| Requirement | Notes |
|---|---|
| Python ≥ 3.11 | |
| [Ollama](https://ollama.com) | Running locally with at least one model pulled |
| ffmpeg | Required by py-cord voice (`apt install ffmpeg` / `brew install ffmpeg`) |
| whisper.cpp *(optional)* | Faster than the Python package; pre-built binaries available |

---

## Quick start

### 1 — Clone & install

```bash
git clone https://github.com/tescolopio/TheWatcher.git
cd TheWatcher
pip install -r requirements.txt
```

### 2 — Create your `.env`

```bash
cp .env.example .env
```

Open `.env` and fill in the required values (see the comments in the file).
The minimum required settings are:

```dotenv
DISCORD_BOT_TOKEN=your_token_here
OBSIDIAN_VAULT_PATH=/absolute/path/to/your/vault
```

### 3 — Pull an Ollama model

```bash
ollama pull mistral   # or llama3, gemma2, etc.
```

### 4 — Run the bot

```bash
python -m src.bot
```

---

## Discord bot setup

1. Go to <https://discord.com/developers/applications> and create a new application.
2. Under **Bot**, enable the **Server Members** and **Voice States** privileged
   intents.
3. Under **OAuth2 → URL Generator**, select the `bot` and `applications.commands`
   scopes.  Add the following bot permissions:
   - Connect
   - Speak
   - Use Voice Activity
   - Read Messages / View Channels
   - Send Messages
4. Copy the generated URL, open it in your browser, and invite the bot to your
   server.
5. Paste the bot token into your `.env` file.

---

## Usage

| Command | Description |
|---|---|
| `/watch` | Join your current voice channel and start recording |
| `/unwatch` | Stop recording and run the full pipeline (transcribe → summarise → save) |

After `/unwatch` the bot will post status messages in the same text channel,
then drop a `.md` note into your Obsidian vault automatically.

---

## Configuration reference

All configuration is via environment variables (loaded from `.env`):

| Variable | Default | Description |
|---|---|---|
| `DISCORD_BOT_TOKEN` | *(required)* | Discord bot token |
| `WHISPER_MODEL` | `base` | Whisper model size: `tiny` / `base` / `small` / `medium` / `large` |
| `WHISPER_CPP_PATH` | *(empty)* | Full path to the `whisper.cpp` binary; leave empty to use the Python package |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Base URL of your Ollama instance |
| `OLLAMA_MODEL` | `mistral` | Ollama model name |
| `OBSIDIAN_VAULT_PATH` | *(required)* | Absolute path to the root of your Obsidian vault |
| `OBSIDIAN_NOTES_FOLDER` | `Session Notes` | Sub-folder inside the vault for session notes |
| `RECORDINGS_DIR` | `/tmp/thewatcher_recordings` | Temporary directory for WAV recordings |

---

## Development

```bash
pip install -r requirements-dev.txt
pytest
```

---

## How it works

1. `/watch` → bot joins your voice channel and starts a `discord.py` PCMSink
   recording session, capturing every speaker's audio separately as PCM.
2. `/unwatch` → recording stops; all per-speaker PCM tracks are mixed into a single
   stereo WAV file saved to `RECORDINGS_DIR`.
3. The WAV file is passed to Whisper (whisper.cpp subprocess or Python package)
   which returns a plain-text transcript.
4. The transcript is sent to Ollama with a structured TTRPG note-taking prompt;
   the model returns a Markdown summary.
5. The summary is written to
   `<OBSIDIAN_VAULT_PATH>/<OBSIDIAN_NOTES_FOLDER>/Session - YYYY-MM-DD.md`
   with YAML front-matter, ready to be picked up by Obsidian.

---

## License

[MIT](LICENSE)

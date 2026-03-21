# Local Deployment Guide

This guide walks through everything needed to run RPG Watcher on your own machine.  For Docker deployment, see [deployment/docker.md](docker.md).

---

## Prerequisites

| Requirement | Version | Install |
|-------------|---------|---------|
| Python | ≥ 3.11 | [python.org](https://www.python.org/downloads/) |
| ffmpeg | any recent | `apt install ffmpeg` / `brew install ffmpeg` / [ffmpeg.org](https://ffmpeg.org) |
| Ollama | any recent | [ollama.com](https://ollama.com) |
| whisper.cpp *(optional)* | any recent | See below |

---

## Step 1 — Create a Discord Bot

1. Open <https://discord.com/developers/applications> and click **New Application**.
2. Name it (e.g. "RPG Watcher") and click **Create**.
3. Select **Bot** in the left sidebar:
   - Click **Reset Token** and copy the token — you will need it for `.env`.
   - Scroll down to **Privileged Gateway Intents** and enable:
     - **Server Members Intent**
     - **Voice States Intent**
4. Select **OAuth2 → URL Generator** in the left sidebar:
   - Under **Scopes**, check `bot` and `applications.commands`.
   - Under **Bot Permissions**, check:
     - Connect
     - Speak
     - Use Voice Activity
     - Read Messages / View Channels
     - Send Messages
5. Copy the generated URL at the bottom, open it in a browser, and invite the bot to your server.

---

## Step 2 — Install RPG Watcher

```bash
git clone https://github.com/tescolopio/rpgwatcher.git
cd rpgwatcher
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

---

## Step 3 — Configure

```bash
cp .env.example .env
```

Open `.env` in any text editor and fill in the required values.  Minimum required:

```dotenv
DISCORD_BOT_TOKEN=your_token_from_step_1
OBSIDIAN_VAULT_PATH=/absolute/path/to/your/vault
```

See the full [configuration reference](../configuration.md) for all options.

---

## Step 4 — Pull an Ollama Model

Start Ollama (if it is not already running as a system service):

```bash
ollama serve &   # Linux/macOS background; or start the Ollama desktop app
```

Pull a model:

```bash
ollama pull mistral   # recommended default (~4 GB download)
# or: ollama pull llama3 / gemma2 / mixtral
```

See [research/llm-models.md](../research/llm-models.md) for a comparison of model options.

---

## Step 5 — (Optional) Install whisper.cpp

Skip this step if you want to use the Python Whisper backend (slower but zero extra setup).

### Linux / macOS

```bash
git clone https://github.com/ggerganov/whisper.cpp.git
cd whisper.cpp
cmake -B build
cmake --build build --config Release
# Download the model
bash models/download-ggml-model.sh base
```

Add to `.env`:

```dotenv
WHISPER_CPP_PATH=/absolute/path/to/whisper.cpp/build/bin/whisper-cli
WHISPER_MODEL=base
```

### Windows

1. Download a pre-built release from <https://github.com/ggerganov/whisper.cpp/releases>
2. Extract the archive to a permanent location (e.g. `C:\whisper.cpp\`)
3. Download the model: run `models\download-ggml-model.cmd base` from the extracted directory
4. Add to `.env`:
   ```dotenv
   WHISPER_CPP_PATH=C:\whisper.cpp\whisper-cli.exe
   WHISPER_MODEL=base
   ```

See [research/whisper-backends.md](../research/whisper-backends.md) for a full backend comparison.

---

## Step 6 — Run the Bot

```bash
python -m src.bot
```

You should see output like:

```
2026-03-03 10:00:00 [INFO] discord.client: Logging in using static token
2026-03-03 10:00:01 [INFO] __main__: Logged in as RPG Watcher#1234 (ID: 123456789)
2026-03-03 10:00:01 [INFO] __main__: Synced 2 slash command(s).
```

---

## Step 7 — Record Your First Session

1. Join a voice channel in your Discord server.
2. In any text channel, type `/watch` — the bot joins your voice channel and starts recording.
3. Play your session.
4. When done, type `/unwatch` — the bot stops recording and runs the pipeline.
5. Watch the status messages; within a minute or two (depending on session length and hardware) the summary appears in the channel and the note lands in your Obsidian vault.

---

## Running as a Background Service

### systemd (Linux)

Create `/etc/systemd/system/rpgwatcher.service`:

```ini
[Unit]
Description=RPG Watcher Discord Bot
After=network-online.target ollama.service
Wants=network-online.target

[Service]
Type=simple
User=rpgwatcher          # create a dedicated user: useradd -r rpgwatcher
WorkingDirectory=/opt/rpgwatcher
ExecStart=/opt/rpgwatcher/.venv/bin/python -m src.bot
EnvironmentFile=/opt/rpgwatcher/.env
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now rpgwatcher
sudo journalctl -u rpgwatcher -f   # follow logs
```

### macOS launchd

Create `~/Library/LaunchAgents/dev.3dtechsolutions.rpgwatcher.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>dev.3dtechsolutions.rpgwatcher</string>
    <key>ProgramArguments</key>
    <array>
        <string>/path/to/rpgwatcher/.venv/bin/python</string>
        <string>-m</string>
        <string>src.bot</string>
    </array>
    <key>WorkingDirectory</key>
    <string>/path/to/rpgwatcher</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>DISCORD_BOT_TOKEN</key>
        <string>your_token_here</string>
        <!-- add other env vars here or load from a file -->
    </dict>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/tmp/rpgwatcher.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/rpgwatcher.err</string>
</dict>
</plist>
```

```bash
launchctl load ~/Library/LaunchAgents/dev.3dtechsolutions.rpgwatcher.plist
```

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| `Failed to sync commands` at startup | Bot missing `applications.commands` scope | Re-invite the bot with the correct URL Generator scopes |
| `/watch` returns "You are not in a voice channel" | User not in any VC | Join a voice channel first |
| `Transcription failed: … model not found` | Whisper model not downloaded | Run `ollama pull` or download GGML model file |
| `Summarisation failed: … connection refused` | Ollama not running | Start Ollama: `ollama serve` |
| Notes not appearing in Obsidian | `OBSIDIAN_VAULT_PATH` wrong | Check path is absolute and the directory exists |
| Bot joins but no audio recorded | Missing `PyNaCl` or `ffmpeg` | `pip install PyNaCl` and install ffmpeg |
| Very slow transcription on CPU | Using `openai-whisper` | Install `whisper.cpp` and set `WHISPER_CPP_PATH` |

For more troubleshooting, see the full troubleshooting guide *(planned for v0.9)*.

# Changelog

All notable changes to RPG Watcher are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
This project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

_Nothing yet — see the [roadmap](docs/roadmap.md) for what's coming next._

---

## [1.0.0] — 2026-03-08

### Added

- **Stable release** — public API surface declared; slash-command names, env-var names, Obsidian note schema, and module public functions are now stable; breaking changes require a new major version
- **`.github/workflows/release.yml`** — full release pipeline triggered on `v*.*.*` tags:
  - `ci-gate` job runs lint + mypy + full test matrix (Python 3.11 & 3.12) as a mandatory gate
  - `build` job produces sdist and wheel; verifies with `twine check`
  - `publish-pypi` job publishes to PyPI via OIDC Trusted Publishing (no API token required)
  - `docker` job builds `linux/amd64` + `linux/arm64` images and pushes to `ghcr.io/tescolopio/rpgwatcher` with semantic-version tags and OCI provenance/SBOM attestations
  - `github-release` job creates a GitHub Release with CHANGELOG notes extracted automatically and dist assets (wheel, sdist, `SHA256SUMS.txt`) attached
- **`.github/workflows/docs.yml`** — deploys the MkDocs Material site to GitHub Pages on every push to `main` and on every release tag; live at <https://tescolopio.github.io/rpgwatcher/>
- `[project.urls]` added to `pyproject.toml` (Homepage, Documentation, Repository, Issues, Changelog)
- `SECURITY.md` — responsible-disclosure instructions for reporting vulnerabilities

### Changed

- `ci.yml` — now also triggers on `v*.*.*` tags so CI runs on every push that creates a release tag
- `pyproject.toml` Development Status classifier: `4 - Beta`; version: `1.0.0`

---

## [0.9.0] — 2026-03-08

### Added

- **`mkdocs.yml`** — MkDocs Material documentation site with full navigation (Home, Getting Started, Architecture, ADRs, Research, Milestones, Roadmap, Contributing, Changelog)
- Deep-purple Material theme with light / dark mode toggle; `pymdownx` extensions for admonitions and code highlighting
- `mkdocs>=1.5.0` and `mkdocs-material>=9.0.0` added to `[project.optional-dependencies] dev` in `pyproject.toml`

---

## [0.8.0] — 2026-03-08

### Added

- **`Dockerfile`** — multi-stage build (`builder` stage installs Python deps; `runner` stage uses `python:3.12-slim` + `ffmpeg` + `libopus0`); non-root `watcher` user; `/app/recordings` and `/app/data` volume mount points
- **`docker-compose.yml`** — `rpgwatcher` service (built from local `Dockerfile`) + `ollama` service (`ollama/ollama:latest`, port `127.0.0.1:11434`); named volumes `recordings`, `db_data`, `ollama_data`; `internal` bridge network; `${OBSIDIAN_VAULT_PATH}` bind-mount for vault
- **`docs/deployment/docker.md`** — comprehensive Docker deployment guide covering quick-start, GHCR image usage, volume management, GPU acceleration, and troubleshooting
- **`.github/workflows/release.yml`** — release pipeline (see v1.0 entry) publishes image to `ghcr.io/tescolopio/rpgwatcher` on every `v*.*.*` tag
- Default container env vars: `RECORDINGS_DIR=/app/recordings`, `RPGWATCHER_DB=/app/data/rpgwatcher.db`, `LOG_FORMAT=json`

---

## [0.7.0] — 2026-03-08

### Added

- **Access control** — `ALLOWED_ROLE_IDS` env var (comma-separated Discord role IDs) restricts `/watch` and `/unwatch` to specific roles; ignored when env var is unset (all members may use the commands)
- **Disk-space guard** — `/watch` refuses to start a recording when available disk space falls below `MIN_FREE_DISK_MB` (default 500 MB); displays a clear error embed
- **`_has_required_role()`** helper in `bot.py` centralises role-membership check
- **`_free_disk_mb()`** helper in `bot.py` returns available megabytes on the recordings filesystem
- `.env.example` documenting `ALLOWED_ROLE_IDS` and `MIN_FREE_DISK_MB`

### Changed

- All state dictionaries (`_active_recordings`, per-guild config, campaign state) verified keyed by `guild_id`; no shared mutable state between guilds
- `/config` command restricted to members with `manage_guild` permission

---

## [0.6.0] — 2026-03-08

### Added

- **`src/audio.py`** — pure-Python PCM audio preprocessing (no `pydub` required):
  - `trim_silence(pcm_bytes, threshold_db, sample_width, channels)` — strips leading/trailing silence frames below the dB threshold
  - `normalize_rms(pcm_bytes, target_db, sample_width)` — scales audio to a target RMS level
  - `preprocess_track(pcm_bytes, *, trim, normalize, silence_threshold_db)` — orchestrates trim + normalize
  - `wrap_pcm_as_wav(pcm_bytes, sample_rate, channels, sample_width)` — wraps raw PCM in an in-memory WAV container
  - `save_pcm_as_wav(pcm_bytes, path, ...)` — writes WAV file to disk
- **`/preview`** command — records a 5-second clip and sends it back to the channel as a WAV attachment for mic-check; auto-stops via `asyncio.create_task`
- `SILENCE_THRESHOLD_DB` env var (default `−40`), `RECORDING_SAMPLE_RATE` env var (default `48000`)
- **`tests/test_audio.py`** — 25+ unit tests for all audio helpers

### Changed

- `src/recorder.py` — `merge_audio_data()` and `finish_recording()` accept `trim_silence` and `normalize` boolean flags that are forwarded to `preprocess_track()` per track
- `src/recorder.py` — new `extract_per_speaker_audio(sink, output_dir, trim_silence, normalize)` function saves individual `speaker_{user_id}.wav` files and returns a `dict[str, Path]`
- `tests/test_recorder.py` — appended tests for preprocessing flags and `extract_per_speaker_audio`

---

## [0.5.0] — 2026-03-08

### Added

- **Character registry** — `/character set <in-game name>`, `/character list`, `/character clear` slash commands; stored per-guild-per-user in the SQLite `characters` table
- **Per-speaker transcription** — each player's WAV track is transcribed individually; segments are labelled `[CharacterName]: "…"` (or Discord username when no character is registered); labelled transcript passed to the summariser
- **`characters`** key in Obsidian note YAML front-matter listing all active character names
- `_SPEAKER_PROMPT_SUFFIX` constant in `src/summarizer.py` that extends the system prompt to leverage the speaker-labelled transcript format and produce a **Party Members** section

### Changed

- `summarize()` accepts optional `speakers: list[str]` parameter; appends speaker suffix to system prompt when provided
- `save_to_obsidian()` accepts optional `characters: list[str]` parameter; adds `characters` key to front-matter
- `tests/test_summarizer.py` — appended speaker-prompt tests
- `tests/test_obsidian.py` — appended characters-in-YAML tests

---

## [0.4.0] — 2026-03-08

### Added

- **Rich embeds** — all pipeline status messages use colour-coded `discord.Embed` objects (🔵 recording, 🟡 processing, 🟢 done, 🔴 error); single "processing" message is edited in-place rather than posting a new message per stage
- **Campaign management** — `/campaign set <name>` and `/campaign clear` slash commands; active campaign stored per-guild in the SQLite database
- **"Open in Obsidian" deep-link** — completion embed includes an `obsidian://open?vault=…&file=…` button
- **Per-guild configuration** — `/config <key> <value>` (guild admin only) allows overriding `OLLAMA_MODEL`, `OBSIDIAN_NOTES_FOLDER`, `campaign`, and `silence_threshold_db` without editing `.env`

### Changed

- `save_to_obsidian()` accepts optional `campaign: str` parameter; stores note in a `campaign/` sub-folder of `OBSIDIAN_NOTES_FOLDER` and includes campaign in YAML front-matter
- `_get_notes_dir()` helper creates the campaign sub-folder if needed
- Discord "typing" indicator shown while each pipeline stage runs; removed redundant per-stage `channel.send()` calls
- `tests/test_obsidian.py` — appended campaign-subfolder and YAML key tests

---

## [0.3.0] — 2026-03-08

### Added

- **`src/database.py`** — SQLite persistence layer (WAL mode):
  - `SessionStatus` enum: `RECORDING`, `PROCESSING`, `DONE`, `FAILED`
  - `init_db()` — idempotent `CREATE TABLE IF NOT EXISTS` for `sessions`, `guild_config`, `characters`
  - Full CRUD for sessions (`create_session`, `update_session`, `get_session`, `get_guild_sessions`, `get_active_recording_sessions`)
  - Guild key-value config store (`get_config`, `set_config`, `delete_config`, `get_all_config`)
  - Character registry (`set_character`, `get_character`, `get_all_characters`, `delete_character`)
- **Ollama retry** — `summarize()` retries the Ollama call up to `OLLAMA_MAX_RETRIES` times (default 3) with exponential back-off starting at `OLLAMA_RETRY_DELAY_S` (default 1.0 s)
- **Fallback Obsidian note** — when Ollama is unreachable after all retries, `save_fallback_note()` writes the raw transcript as a Markdown note tagged `#needs-summary` with a `> [!warning]` callout
- **`/sessions` command** — lists recent sessions for the guild with status emoji (🔴 recording, 🟡 processing, ✅ done, ❌ failed)
- **`/status` command** — displays bot latency, Ollama connectivity, Whisper backend in use, vault path, and available disk space
- **Structured JSON logging** — opt-in via `LOG_FORMAT=json`; every log record emits a JSON object; recording sessions attach a correlation ID to all log lines
- **Orphaned-session recovery** — `on_ready` marks any sessions left in `RECORDING` state as `FAILED` after a bot restart
- `RPGWATCHER_DB` env var to configure the SQLite file path (default `rpgwatcher.db`)
- **`tests/test_database.py`** — 32+ unit tests for all database operations
- `tests/test_summarizer.py` — appended retry-logic tests

### Changed

- `src/bot.py` — `_active_recordings` type changed from `dict[int, discord.VoiceClient]` to `dict[int, tuple[discord.VoiceClient, str]]` (now stores voice client + session UUID)
- Bot calls `init_db()` at startup
- `_on_recording_finished` updates session status at each pipeline stage; writes fallback note on Ollama failure

---

## [0.2.0] — 2026-03-04

### Added

- **`pyproject.toml`** (PEP 621) — single source of truth for project metadata and dependencies, replacing ad-hoc `requirements*.txt` files; exposes a `rpgwatcher` console-script entry point
- **`src/py.typed`** — PEP 561 marker enabling downstream consumers to benefit from the package's type annotations
- **`ruff`** configuration in `pyproject.toml` — replaces flake8 / black for linting and formatting
- **`.pre-commit-config.yaml`** — runs `ruff`, `mypy --strict`, and `pytest` on staged/pushed files; also includes standard pre-commit-hooks (trailing whitespace, YAML/TOML validation, merge-conflict detection)
- **`.github/workflows/ci.yml`** — CI pipeline that lints, type-checks, and runs the test suite on `ubuntu-latest` for Python 3.11 and 3.12; enforces ≥ 80 % line coverage via `pytest-cov`
- **`tests/test_bot.py`** — unit tests for `bot.py` covering `on_ready`, `watch`, `unwatch`, and all branches of `_on_recording_finished` using `pytest-asyncio` and `unittest.mock`
- **`tests/test_integration.py`** — end-to-end smoke tests that exercise the full record → transcribe → summarise → Obsidian pipeline with mocked external services
- CI badge added to `README.md`

### Changed

- **`src/bot.py`** — added `None` guard for `bot.user` in `on_ready`; added `None` guard for `interaction.channel` in `/watch`; added `if __name__ == "__main__"` entry point; updated `_on_recording_finished` to accept `Optional[Messageable]` for `channel`
- **`src/recorder.py`** — typed `audio_data` parameter as `dict[Any, Any]` for mypy strict compliance
- **`src/transcriber.py`** — added explicit `str()` cast on whisper result to satisfy mypy strict mode
- **`src/summarizer.py`** — added explicit `list[dict[str, Any]]` type for the messages list; cast `response.message.content` to `str`

### Developer experience

- `[project.optional-dependencies]` `dev` group consolidates all development tools: `pytest`, `pytest-asyncio`, `pytest-cov`, `mypy`, `ruff`, `pre-commit`
- `pyproject.toml` `[tool.pytest.ini_options]` enforces `asyncio_mode = "auto"` and `--cov-fail-under=80`

---

## [0.1.0] — 2026-03-03

### Added

- `/watch` slash command — joins the caller's Discord voice channel and starts a `PCMSink` recording session via py-cord
- `/unwatch` slash command — stops the recording and runs the full pipeline: merge → transcribe → summarise → save
- **`src/recorder.py`** — per-user PCM capture; zero-pad-and-sum stereo mixer; WAV serialisation at 48 kHz / 16-bit / stereo (Discord's native Opus decode format)
- **`src/transcriber.py`** — dual-backend transcription: `whisper.cpp` subprocess when `WHISPER_CPP_PATH` is configured, otherwise `openai-whisper` Python package; backend selected automatically at runtime
- **`src/summarizer.py`** — TTRPG-focused structured Markdown summary via a local Ollama model; system prompt produces five fixed sections (Session Overview, Key Events, NPC Interactions, Player Decisions, Cliffhangers / Open Threads)
- **`src/obsidian.py`** — dated Markdown notes with YAML front-matter written directly into an Obsidian vault; collision-safe filename generation
- Environment variable configuration via `.env` / `python-dotenv` (`DISCORD_BOT_TOKEN`, `OBSIDIAN_VAULT_PATH`, `OBSIDIAN_NOTES_FOLDER`, `RECORDINGS_DIR`, `WHISPER_MODEL`, `WHISPER_CPP_PATH`, `OLLAMA_BASE_URL`, `OLLAMA_MODEL`)
- Unit test suite covering all four core modules (`test_recorder`, `test_transcriber`, `test_summarizer`, `test_obsidian`)
- `README.md` with quick-start instructions, Discord bot setup, and configuration reference
- `docs/` directory: `index.md`, `architecture.md`, `configuration.md`, `contributing.md`, `roadmap.md`, milestone detail docs for v0.2–v0.4

---

[Unreleased]: https://github.com/tescolopio/rpgwatcher/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/tescolopio/rpgwatcher/compare/v0.9.0...v1.0.0
[0.9.0]: https://github.com/tescolopio/rpgwatcher/compare/v0.8.0...v0.9.0
[0.8.0]: https://github.com/tescolopio/rpgwatcher/compare/v0.7.0...v0.8.0
[0.7.0]: https://github.com/tescolopio/rpgwatcher/compare/v0.6.0...v0.7.0
[0.6.0]: https://github.com/tescolopio/rpgwatcher/compare/v0.5.0...v0.6.0
[0.5.0]: https://github.com/tescolopio/rpgwatcher/compare/v0.4.0...v0.5.0
[0.4.0]: https://github.com/tescolopio/rpgwatcher/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/tescolopio/rpgwatcher/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/tescolopio/rpgwatcher/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/tescolopio/rpgwatcher/releases/tag/v0.1.0

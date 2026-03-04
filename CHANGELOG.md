# Changelog

All notable changes to TheWatcher are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
This project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

_Nothing yet — see the [roadmap](docs/roadmap.md) for what's coming next._

---

## [0.2.0] — 2026-03-04

### Added

- **`pyproject.toml`** (PEP 621) — single source of truth for project metadata and dependencies, replacing ad-hoc `requirements*.txt` files; exposes a `thewatcher` console-script entry point
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

[Unreleased]: https://github.com/tescolopio/TheWatcher/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/tescolopio/TheWatcher/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/tescolopio/TheWatcher/releases/tag/v0.1.0

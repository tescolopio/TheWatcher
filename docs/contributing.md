# Contributing to TheWatcher

Thank you for your interest in contributing!  This document covers how to set up your development environment, run tests, and submit changes.

---

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Running Tests](#running-tests)
- [Code Style](#code-style)
- [Submitting Changes](#submitting-changes)
- [Issue Reporting](#issue-reporting)
- [Roadmap & Good First Issues](#roadmap--good-first-issues)

---

## Code of Conduct

This project follows the [Contributor Covenant Code of Conduct](https://www.contributor-covenant.org/version/2/1/code_of_conduct/).  By participating, you agree to abide by its terms.  Report unacceptable behaviour to the maintainers.

---

## Getting Started

1. **Fork** the repository on GitHub, then clone your fork:

   ```bash
   git clone https://github.com/<your-username>/TheWatcher.git
   cd TheWatcher
   ```

2. **Verify prerequisites:**

   | Tool | Minimum version | Check |
   |------|----------------|-------|
   | Python | 3.11 | `python --version` |
   | ffmpeg | any recent | `ffmpeg -version` |
   | Ollama | any recent | `ollama --version` |

---

## Development Setup

### 1. Create a virtual environment

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
```

### 2. Install all dependencies (including dev tools)

```bash
pip install -r requirements-dev.txt
```

### 3. Configure the bot

```bash
cp .env.example .env
# Edit .env — at minimum set DISCORD_BOT_TOKEN and OBSIDIAN_VAULT_PATH
```

### 4. (Optional) Install pre-commit hooks

> ⚠️ Pre-commit hooks are coming in v0.2.  Once added, run:

```bash
pre-commit install
```

Hooks run `ruff` (lint + format) and `mypy` (type check) on every commit.

---

## Running Tests

```bash
# Run the full test suite
pytest

# With coverage report
pytest --cov=src --cov-report=term-missing

# Run a specific test file
pytest tests/test_recorder.py -v

# Run a specific test
pytest tests/test_recorder.py::test_merge_single_track_passthrough -v
```

All tests use only standard library mocks — no real Discord connection, Ollama server, or Whisper model is required.

### Test philosophy

- **Unit tests** for every public function in every module under `src/`.
- **No real I/O** in tests — mock `subprocess.run`, `ollama.Client`, and filesystem operations where needed.
- **`tmp_path` fixture** for any test that writes to disk.
- Tests must be deterministic and pass in CI without external services.

---

## Code Style

| Concern | Tool | Config |
|---------|------|--------|
| Formatting | `ruff format` | `pyproject.toml` (coming v0.2) |
| Linting | `ruff check` | `pyproject.toml` (coming v0.2) |
| Type checking | `mypy --strict` | `pyproject.toml` (coming v0.2) |

Until `pyproject.toml` is added (v0.2), follow these conventions manually:

- **Imports:** stdlib → third-party → local (`src.*`), each group separated by a blank line.
- **Docstrings:** Google-style; every public function and class must have one.
- **Type annotations:** required on all function signatures; `from __future__ import annotations` is not used.
- **Line length:** 99 characters.
- **No bare `except:`** — always catch a specific exception type.

---

## Submitting Changes

### Branch naming

| Type | Convention | Example |
|------|-----------|---------|
| Feature | `feat/<short-description>` | `feat/per-speaker-transcription` |
| Bug fix | `fix/<short-description>` | `fix/disk-space-check` |
| Docs | `docs/<short-description>` | `docs/configuration-reference` |
| Chore | `chore/<short-description>` | `chore/add-precommit` |

### Pull request checklist

Before opening a PR, confirm:

- [ ] All existing tests pass (`pytest`)
- [ ] New behaviour is covered by new tests
- [ ] No new `mypy` strict-mode errors
- [ ] Docstrings added/updated for changed functions
- [ ] `CHANGELOG.md` entry added under `[Unreleased]`
- [ ] PR title follows [Conventional Commits](https://www.conventionalcommits.org/): `feat:`, `fix:`, `docs:`, `chore:`, etc.

### Commit messages

Use Conventional Commits format:

```
<type>(<scope>): <short summary>

[optional body]

[optional footer]
```

Examples:
```
feat(summarizer): add configurable system prompt via env var
fix(recorder): prevent crash when no users speak during session
docs(contributing): add pre-commit setup instructions
```

---

## Issue Reporting

When filing a bug report, include:

1. **Operating system** and Python version (`python --version`)
2. **Bot version** / git commit hash
3. **Steps to reproduce** — the exact Discord commands used
4. **Expected vs. actual behaviour**
5. **Relevant log output** — run the bot with `LOG_LEVEL=DEBUG` and paste the relevant section
6. **`.env` (redact your bot token)** — which optional settings are non-default

Feature requests are welcome — reference the [roadmap](roadmap.md) to check whether the feature is already planned.

---

## Roadmap & Good First Issues

See [roadmap.md](roadmap.md) for the full plan to v1.0.

Good starting points for first-time contributors:

| Task | Milestone | Difficulty |
|------|-----------|-----------|
| Add `.env.example` | v0.2 | ⭐ Easy |
| Add `CHANGELOG.md` | v0.2 | ⭐ Easy |
| Write unit tests for `bot.py` | v0.2 | ⭐⭐ Medium |
| Add `/status` command | v0.3 | ⭐⭐ Medium |
| Add disk-space check before recording | v0.3 | ⭐⭐ Medium |
| Add rich Discord embeds | v0.4 | ⭐⭐ Medium |
| Add `Dockerfile` | v0.8 | ⭐⭐⭐ Hard |

If you are working on something, comment on the relevant GitHub issue so we avoid duplicate effort.

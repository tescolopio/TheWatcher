# RPG Watcher Documentation

Welcome to the RPG Watcher documentation.  Use the links below to navigate.

---

## Overview

RPG Watcher is an open-source, **privacy-first** Discord bot that records your tabletop RPG voice sessions, transcribes them entirely on your own hardware, and generates a structured Markdown summary that lands directly in your Obsidian vault.

```
Voice channel → PCMSink recording → Whisper (local) → Ollama (local) → Obsidian vault
```

No cloud services.  No subscriptions.  No data leaves your machine.

---

## Getting Started

| Resource | Description |
|----------|-------------|
| [README](../README.md) | Quick-start, Discord bot setup, usage |
| [Local Deployment Guide](deployment/local.md) | Step-by-step setup including systemd / launchd service |
| [Configuration Reference](configuration.md) | Every environment variable with types, defaults, and examples |

---

## Development

| Resource | Description |
|----------|-------------|
| [Architecture](architecture.md) | Data flow, module responsibilities, concurrency model, directory layout |
| [Contributing](contributing.md) | Dev setup, code style, test philosophy, PR checklist |
| [Roadmap](roadmap.md) | Full plan: v0.1 MVP → v1.0 stable Discord bot → v2.0 standalone application |

---

## User Stories

The complete feature backlog expressed as user stories with acceptance criteria, organised by release track:

| Document | Track | Stories |
|----------|-------|---------|
| [Index & Personas](user-stories/index.md) | Both | Persona definitions, ID system, status tags |
| [v1.0 Discord Bot](user-stories/v1-discord-bot.md) | v0.1 – v1.0 | Recording, error recovery, speaker ID, multi-guild, distribution |
| [v2.0 Standalone Application](user-stories/v2-standalone.md) | v1.1 – v2.0 | Platform abstraction, Web UI, mic/loopback/Zoom sources, voice profiles, output adapters |

---

## Architecture Decision Records

Significant technology and design choices, with context and alternatives considered:

| ADR | Decision |
|-----|----------|
| [ADR-0001](adr/0001-local-only-architecture.md) | Local-only, privacy-first architecture |
| [ADR-0002](adr/0002-pycord-discord-library.md) | py-cord as the Discord library |
| [ADR-0003](adr/0003-dual-whisper-backends.md) | Dual Whisper transcription backends |
| [ADR-0004](adr/0004-ollama-for-llm.md) | Ollama for local LLM inference |
| [ADR-0005](adr/0005-obsidian-markdown-notes.md) | Obsidian vault as the note-taking target |

---

## Research

Benchmarks, findings, and technology evaluations that informed design decisions:

| Document | Contents |
|----------|---------|
| [Whisper Backends](research/whisper-backends.md) | openai-whisper vs whisper.cpp: benchmarks, model size guide, audio format notes |
| [LLM Models](research/llm-models.md) | Ollama model comparison for TTRPG summarisation: quality, speed, RAM requirements |
| [Discord Voice Recording](research/discord-voice.md) | py-cord PCMSink internals, audio merging strategy, known limitations |
| [Standalone Architecture](research/standalone-architecture.md) | v1.1–v2.0 engineering challenges: AudioSource protocol, FastAPI state sync, cross-platform loopback, diarization, OAuth2 local flows, PCM mixing, packaging, adaptive `num_ctx` |

---

## Milestone Detail Docs

Detailed task breakdowns for near-term milestones:

| Milestone | Focus | Detail Doc |
|-----------|-------|-----------|
| v0.2 | Foundation & Developer Experience | [v0.2-foundation.md](milestones/v0.2-foundation.md) |
| v0.3 | Reliability & Error Recovery | [v0.3-reliability.md](milestones/v0.3-reliability.md) |
| v0.4 | User Experience & Campaigns | [v0.4-ux-campaigns.md](milestones/v0.4-ux-campaigns.md) |

Further milestone detail docs will be added as earlier milestones approach completion.

---

## Project Standards

| Document | Purpose |
|----------|---------|
| [CHANGELOG](../CHANGELOG.md) | Full history of user-visible changes (Keep a Changelog format) |
| [CODE_OF_CONDUCT](../CODE_OF_CONDUCT.md) | Contributor Covenant — community standards and enforcement |
| [SECURITY](../SECURITY.md) | Vulnerability reporting process and scope |
| [Contributing](contributing.md) | Development workflow, PR requirements |

---

## Project Links

- [GitHub Repository](https://github.com/tescolopio/RPG Watcher)
- [Issue Tracker](https://github.com/tescolopio/RPG Watcher/issues)
- [Discussions](https://github.com/tescolopio/RPG Watcher/discussions)

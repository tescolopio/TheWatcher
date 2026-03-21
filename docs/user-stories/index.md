# User Stories — Index

This folder contains the full user story backlog for RPG Watcher, organised by release track.

| File | Track | Milestones |
|------|-------|------------|
| [v1-discord-bot.md](v1-discord-bot.md) | Discord bot | v0.1 – v1.0 |
| [v2-standalone.md](v2-standalone.md) | Standalone application | v1.1 – v2.0 |

---

## How to read a story

Each story follows this format:

```
### US-NNN — Short title

**As a** [persona],
**I want to** [capability],
**so that** [benefit].

**Acceptance criteria:**
- [ ] ...

**Milestone:** vX.X
**Notes:** Edge cases, open questions, links to related ADRs or research.
```

Acceptance criteria use `[ ]` checkboxes so they can be tracked in a PR description or issue.

---

## Story ID System

| Range | Track |
|-------|-------|
| US-001 – US-099 | v1.0 Discord bot track |
| US-100 – US-199 | v2.0 Standalone track |

IDs are permanent.  A story that is split, superseded, or deferred keeps its original ID; the replacement or successor gets a new one.

---

## Personas

### v1.0 Track

| Persona | Who they are | Technical level |
|---------|-------------|-----------------|
| **Sam (GM)** | Game Master; installs and operates the bot for their group; owns the Discord server or has admin rights | Comfortable with a `.env` file and basic CLI |
| **Alex (Player)** | Session participant; interacts with the bot only through Discord; does not configure anything | Non-technical |
| **Jordan (Server Admin)** | Owns or co-administers the Discord server; concerned with access control, multi-guild isolation, and bot permissions | Moderately technical |
| **Casey (Campaign Manager)** | Tracks one or more long-running campaigns; cares about note organisation, tagging, and archive searchability | Non-technical to moderately technical |

### v2.0 Track

| Persona | Who they are | Technical level |
|---------|-------------|-----------------|
| **River (Non-Discord User)** | Plays TTRPG via Zoom, Google Meet, or in person; has never used Discord; wants the same note-generation capability | Non-technical |
| **Morgan (Archivist)** | Has a backlog of existing session recordings they never got around to processing; wants batch-convert to notes | Moderately technical |
| **Taylor (Solo Player)** | Plays solo RPGs or journals via voice; no group, no Discord; wants a personal session log | Non-technical |
| **Quinn (Multi-Group GM)** | Runs two or three separate campaigns for different groups; wants complete separation between them from one install | Moderately technical |

---

## Status Tags

| Tag | Meaning |
|-----|---------|
| ✅ Implemented | Story is done and the feature is live |
| 📋 Planned | Story is accepted and assigned to a milestone |
| 💭 Draft | Story is written but not yet reviewed or assigned |
| ⏸ Deferred | Moved to a later milestone; reason noted |

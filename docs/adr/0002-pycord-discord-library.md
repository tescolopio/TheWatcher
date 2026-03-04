# ADR-0002 — py-cord as the Discord Library

**Date:** 2026-01-18  
**Status:** Accepted

---

## Context

TheWatcher needs to connect to the Discord Gateway, join voice channels, and capture per-user audio.  The choice of Discord library determines:

- How the bot registers and handles slash commands
- Whether per-user PCM audio capture is available at all
- The maturity and maintenance status of the dependency
- Python version compatibility

---

## Decision

Use **[py-cord](https://github.com/Pycord-Development/pycord)** (`py-cord[voice]`) as the Discord library.

---

## Rationale

py-cord is a maintained fork of `discord.py` that adds first-class support for Discord's Application Commands (slash commands) and, critically, ships `discord.sinks` — a voice recording API that captures per-user PCM audio directly from the Discord Opus decoder.

The `PCMSink` class provided by `discord.sinks` captures 48 kHz / 16-bit / stereo PCM per-user, which is exactly the format needed to feed Whisper.  Without this capability, recording individual speakers would require writing a custom Opus decoding layer.

---

## Alternatives Considered

### `discord.py` (original)

- `discord.py` development was abandoned in 2021 and resumed in 2022 as `discord.py 2.x`
- As of this ADR, `discord.py 2.x` does not ship `discord.sinks` for per-user voice recording
- Slash command support (`app_commands`) is present but the API differs from py-cord's `bot.tree`
- ❌ No built-in per-user PCM voice capture

### `hikari` + `hikari-arc`

- Modern, well-architected async library
- ❌ No built-in voice recording support; voice functionality is split across unmaintained plugins
- Would require building the entire voice recording pipeline from scratch

### `nextcord`

- Another maintained discord.py fork
- ❌ No `discord.sinks` equivalent; voice recording not a supported feature

### Direct WebSocket / REST

- ❌ Enormous implementation surface; not viable for a small project

---

## Consequences

**Positive:**
- `PCMSink` provides per-user audio capture with zero custom Opus decoding code
- Slash command registration is straightforward via `bot.tree`
- Mature fork with active maintenance

**Negative:**
- Creates a dependency on a fork that may diverge from `discord.py` in breaking ways
- `discord.sinks` API surface is small and not heavily documented; edge cases must be discovered experimentally
- `PyNaCl` (libsodium binding) is a required transitive dependency for voice

**Monitoring:** Review py-cord release notes and discord.py evolution at each minor version bump.  If `discord.py` ships `discord.sinks`-equivalent functionality, evaluate migrating back.

# ADR-0001 — Local-only, Privacy-first Architecture

**Date:** 2026-01-15  
**Status:** Accepted

---

## Context

TheWatcher is intended for tabletop RPG groups who want to capture and summarise their voice sessions.  Session recordings contain private conversations, character voices, real names, and in some cases sensitive personal information shared in the social context of a game.

The majority of comparable tools (Otter.ai, Fireflies.ai, Discord bots calling OpenAI, etc.) send audio data to cloud APIs for transcription and summarisation.  This requires trusting third-party services with private recordings, creates a subscription cost, and introduces an internet-connectivity dependency.

The core question: should TheWatcher ever send audio, transcripts, or summaries to any external service?

---

## Decision

**TheWatcher will never transmit audio, transcripts, or summaries to any service outside the user's own machine or local network.**

Specifically:
- Transcription is performed by Whisper running locally — either via the `whisper.cpp` binary or the `openai-whisper` Python package.
- Summarisation is performed by a model served by a locally running Ollama instance.
- Notes are written to the local filesystem (Obsidian vault), not to any cloud sync endpoint controlled by the project.
- No telemetry, analytics, or crash-reporting is collected.

---

## Rationale

1. **Trust** — Users can self-audit all code paths; nothing is transmitted to a "black box" cloud service.
2. **Cost** — No API tokens, no usage fees, no rate limits.
3. **Availability** — Works offline or in a LAN-only environment.
4. **Longevity** — The bot will continue to work even if any cloud vendor changes pricing, API terms, or shuts down.
5. **TTRPG community alignment** — The hobby has a strong DIY ethos; local hosting is a feature, not a constraint.

---

## Alternatives Considered

### OpenAI Whisper API + GPT for summarisation

- ❌ Sends audio and text to OpenAI servers
- ❌ Requires an API key and incurs per-minute / per-token costs
- ❌ Breaks when offline or the API is unavailable
- ✅ Higher transcription accuracy for some accents / languages

### Discord-native transcription (if/when available)

- ❌ Still handled by Discord's servers (not local)
- ❌ No programmatic access to the raw transcript at time of writing
- Could be reconsidered if Discord exposes a privacy-controlled local option

### Hybrid: local recording + optional cloud summarisation

- Rejected as unnecessarily complex for v1.0; would require maintaining two code paths and a consent mechanism.  Can be revisited post-v1.0 as an opt-in.

---

## Consequences

**Positive:**
- Strong privacy guarantee by construction — no policy needed, no trust required
- No dependency on external service availability or pricing

**Negative:**
- Users must have sufficient hardware to run Whisper and an LLM locally (8 GB RAM minimum realistic floor)
- Transcription and summarisation quality is bounded by locally available models
- Initial setup is more involved (install Ollama, pull a model, optionally build whisper.cpp)

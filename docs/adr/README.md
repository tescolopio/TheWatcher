# Architecture Decision Records

This directory captures significant architectural and technology decisions made during the design and development of TheWatcher.

Each ADR is a short document that explains **what** was decided, **why** it was decided that way, and what **alternatives** were considered and rejected.  Once accepted, an ADR is immutable — if a decision is reversed, a new ADR supersedes it and the old one is marked as superseded.

---

## Index

| ID | Title | Status |
|----|-------|--------|
| [ADR-0001](0001-local-only-architecture.md) | Local-only, privacy-first architecture | Accepted |
| [ADR-0002](0002-pycord-discord-library.md) | py-cord as the Discord library | Accepted |
| [ADR-0003](0003-dual-whisper-backends.md) | Dual Whisper transcription backends | Accepted |
| [ADR-0004](0004-ollama-for-llm.md) | Ollama for local LLM inference | Accepted |
| [ADR-0005](0005-obsidian-markdown-notes.md) | Obsidian vault as the note-taking target | Accepted |

---

## Format

Each ADR follows this template:

```markdown
# ADR-NNNN — Title

**Date:** YYYY-MM-DD  
**Status:** Proposed | Accepted | Deprecated | Superseded by ADR-XXXX

## Context
What is the problem or requirement driving this decision?

## Decision
What did we decide to do?

## Rationale
Why did we make this choice?

## Alternatives Considered
What else did we look at, and why did we reject it?

## Consequences
What are the positive and negative outcomes of this decision?
```

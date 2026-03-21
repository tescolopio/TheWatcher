# ADR-0004 — Ollama for Local LLM Inference

**Date:** 2026-01-22  
**Status:** Accepted

---

## Context

RPG Watcher needs to take a raw voice transcript and produce a structured, TTRPG-flavoured Markdown summary.  This is a natural-language generation task that benefits from a large language model.

Given ADR-0001 (local-only architecture), the LLM must run on the user's own hardware.  The question is how to manage model download, serving, and a Python client.

---

## Decision

Use **[Ollama](https://ollama.com)** as the local LLM inference server, accessed via the official `ollama` Python client library.

---

## Rationale

1. **Turn-key model serving** — Ollama handles model download (`ollama pull mistral`), GGUF quantisation, GPU acceleration (if available), and an OpenAI-compatible REST API.  Users get a working LLM backend with a single command.
2. **Model flexibility** — Any model in the Ollama library can be used by changing `OLLAMA_MODEL`.  Users are not locked into a specific model or quantisation level.
3. **Official Python client** — The `ollama` pip package provides a typed Python interface with auto-retry and streaming; no HTTP boilerplate needed.
4. **Active ecosystem** — Ollama is widely used and documented; troubleshooting resources are plentiful.
5. **GPU optional** — Ollama runs on CPU alone; GPU support is transparent and automatic when available.

---

## Alternatives Considered

### Direct `llama.cpp` Python bindings (`llama-cpp-python`)

- ✅ No separate server process; model loaded directly in-process
- ❌ Requires native compilation of `llama.cpp` (complex on Windows)
- ❌ No model management; user must download GGUF files manually
- ❌ Higher memory overhead when the model is loaded for each summarisation call (no persistent server)

### `transformers` (Hugging Face)

- ✅ Massive model selection
- ❌ PyTorch dependency (already pulled in by `openai-whisper`, but a second large dep adds maintenance burden)
- ❌ No built-in server/daemon; model loaded per call unless the user writes their own serving layer
- ❌ No equivalent of `ollama pull` for easy model management

### `lm-studio` API (OpenAI-compatible)

- ✅ Nice GUI; popular with non-developers
- ❌ Closed-source application; not programmatically installable
- ❌ Not suitable as a required dependency in an open-source project

### OpenAI API (cloud)

- ❌ Violates ADR-0001 (data leaves the machine)

---

## Consequences

**Positive:**
- Users with Ollama already installed (common in the local-AI community) have zero additional setup beyond `ollama pull <model>`
- Model upgrades are one command; the bot picks them up automatically
- Ollama's context-window management and prompt caching benefit long transcripts

**Negative:**
- Ollama must be running as a separate process before the bot starts
- If Ollama is not installed or not running, the pipeline fails at the summarisation stage (mitigated by ADR-0001-aligned fallback in v0.3: save transcript as a raw note tagged `#needs-summary`)
- Ollama adds a runtime process dependency that users must manage (added to pre-flight check in `/status` command, planned v0.3)

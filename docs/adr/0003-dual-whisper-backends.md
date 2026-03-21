# ADR-0003 — Dual Whisper Transcription Backends

**Date:** 2026-01-20  
**Status:** Accepted

---

## Context

Whisper speech recognition is available in two forms relevant to this project:

1. **`openai-whisper`** — OpenAI's original Python package.  Installs via pip; no native compilation required; uses PyTorch under the hood; works on any platform Python supports.
2. **`whisper.cpp`** — A C++ reimplementation by Georgi Gerganov.  Must be compiled from source (or a pre-built binary used); runs entirely on CPU with no Python/PyTorch dependency; significantly faster and lighter on RAM at equivalent accuracy.

Neither option is universally better: `openai-whisper` has zero extra setup steps, while `whisper.cpp` can be 5–10× faster on the same hardware and does not require a PyTorch installation (which pulls in ~2–3 GB of wheels).

The question: should RPG Watcher support one backend or both?

---

## Decision

Support **both backends** with automatic selection at runtime.

Selection logic:

```
WHISPER_CPP_PATH set AND file is executable?
  → use whisper.cpp subprocess
  else
  → use openai-whisper Python package
```

Both backends are exposed through the same `transcribe(audio_path) -> str` public interface in `src/transcriber.py`.

---

## Rationale

1. **Zero-friction onboarding** — Users who just want to try the bot can `pip install -r requirements.txt` and have a working transcription backend immediately, without compiling anything.
2. **Power-user path** — Users who want the best performance can install whisper.cpp and set `WHISPER_CPP_PATH`; the bot upgrades automatically.
3. **No user code change** — Backend selection is fully configuration-driven; switching between backends is a one-line `.env` change.
4. **Abstraction boundary** — `src/transcriber.py` is the single module that knows about backends; the rest of the codebase calls `transcribe()` and does not care how it works.

---

## Alternatives Considered

### Only `openai-whisper`

- ✅ Simpler code, single dependency
- ❌ 5–10× slower than whisper.cpp on CPU-only hardware
- ❌ Requires PyTorch (~2–3 GB install size)
- ❌ Forces power users to use a slower backend with no escape hatch

### Only `whisper.cpp`

- ✅ Fastest possible transcription
- ❌ Requires compilation (or finding a pre-built binary for the user's platform)
- ❌ Hard blocker for Windows users or users without build tools
- ❌ Model files must be downloaded separately in GGML format

### `faster-whisper` (CTranslate2 backend)

- ✅ Fast Python-native option; 2–4× faster than `openai-whisper`, comparable to whisper.cpp
- ❌ Another optional dependency to document and maintain
- Could be added as a third backend in a future ADR without breaking the abstraction

---

## Consequences

**Positive:**
- Broadest possible hardware compatibility
- Users are not forced to choose upfront; the default just works

**Negative:**
- Two code paths to maintain and test
- `whisper.cpp` model file path convention (`../models/ggml-<model>.bin`) is relatively rigid; changes to the whisper.cpp binary layout require updates here
- Users must know to set `WHISPER_CPP_PATH` to benefit from the faster backend — discoverability relies on documentation

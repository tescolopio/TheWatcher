# Research: Standalone Application Architecture

**Status:** 🔬 Active — all queries open; work begins after v1.0 ships  
**Informs:** [roadmap.md v1.1–v2.0](../roadmap.md#beyond-v10--standalone-application-vision-), `src/` (future platform-abstraction refactor)

> This document covers the engineering challenges specific to transforming RPG Watcher from a Discord-centric bot into a self-contained application that works for any group, on any voice platform, without requiring Discord. Queries are grouped by the roadmap phase in which they must be resolved.

---

## Query Status Key

| Symbol | Meaning |
|--------|---------|
| ✅ | Answered — measured or established by analysis |
| 🔬 | Open — experiment designed but not yet run |
| 💭 | Hypothesis — inferred from documentation or prior art; not measured by us |

---

## Phase 1 — Architectural Abstraction & Data Flow

### Q1 — How to unify "per-user" and "mixed-stream" audio data models in a single protocol? 🔬

**Milestone:** v1.1

**Context:** Discord provides pre-segmented PCM buffers keyed by `user_id` — speaker attribution is free at the transport layer. System microphones provide a single interleaved stream where speaker identity must be computed via diarization. The `AudioSource` protocol must abstract this difference so the downstream pipeline (transcription, character attribution, note generation) is identical regardless of source.

**Query:** Define a protocol that handles both push-based segmented data (Discord) and pull-based continuous streams (System Mic) without exposing the difference to the pipeline.

**Hypothesis:** An `AudioSource` that yields a stream of `AudioSegment` objects — each carrying raw PCM, a `speaker_id` (either a Discord `user_id` int or a diarization-assigned string), `speaker_confidence` (1.0 for Discord, 0.0–1.0 for diarized), and a `wall_clock_start` timestamp — allows the downstream pipeline to remain fully source-agnostic.

**Proposed protocol:**

```python
from typing import AsyncIterator, Protocol
from dataclasses import dataclass

@dataclass
class AudioSegment:
    pcm: bytes                    # 16-bit LE, 16 kHz mono (Whisper-native)
    speaker_id: int | str         # user_id (Discord) or embedding-cluster label (mic)
    speaker_confidence: float     # 1.0 for transport-identified; 0.0–1.0 for diarized
    wall_clock_start: float       # monotonic time this segment began
    wall_clock_end: float

class AudioSource(Protocol):
    async def start(self) -> None: ...
    async def stop(self) -> None: ...
    def segments(self) -> AsyncIterator[AudioSegment]: ...
    # Called before start() to declare known speaker IDs → display names
    async def register_speakers(self, profiles: dict[str | int, str]) -> None: ...
```

**Decision output:** This protocol definition gates the v1.1 `AudioSource` interface ADR. Once locked, Discord, FileUpload, SystemMic, and Loopback sources can be implemented independently.

**Open sub-questions:**
- For Discord, `wall_clock_start` must be derived from the join-timestamp pre-padding fix (see [discord-voice.md Q2](discord-voice.md#q2)). Confirm that PCM byte offset can be reliably converted to a wall-clock position given the 48 kHz, 2-channel, 2-byte sample format.
- For mixed stream sources, what is the minimum segment length that makes speaker confidence reliable? Too short (< 500 ms) and embedding models produce low-confidence results; too long introduces transcript-alignment latency.

---

### Q2 — What is the optimal method for non-blocking state synchronization between a FastAPI web server and a long-running recording thread? 🔬

**Milestone:** v1.2

**Context:** The recording pipeline does heavy CPU work (VAD, chunked transcription, embedding computation) in `asyncio.to_thread` calls. The Web UI needs a live view of the running session — active speakers, elapsed time, live transcript lines as they complete — without these reads corrupting write state or blocking the pipeline.

**Query:** Investigate shared-memory vs. local-persistence approaches for "live" session data accessible from the FastAPI process while the recording thread writes to it.

**Candidate approaches:**

| Approach | Mechanism | Live update latency | Crash safety | Complexity |
|----------|-----------|--------------------|--------------| -----------|
| **In-process `asyncio.Queue`** | Web SSE endpoint drains a queue that the pipeline writes to | < 100 ms | Lost on crash | Low |
| **SQLite WAL mode** | Pipeline writes each completed chunk transcript as a row; Web UI polls | 1–5 s | ✅ Survived | Low |
| **Redis pub/sub** | Pipeline publishes events; Web SSE subscribes | < 100 ms | Lost on crash (unless AOF) | Medium — external dep |
| **`multiprocessing.shared_memory`** | Shared buffer for status struct (stage, elapsed, speaker count) | < 50 ms | Lost on crash | Medium |
| **File-based event log** | Pipeline appends JSON lines to `session-{id}.jsonl`; Web UI tails | 1–2 s | ✅ Survived | Low |

**Hypothesis:** SQLite WAL mode is the right baseline: it survives process crashes (the transcript is on disk), requires no external dependency, and 1–5 second polling latency is acceptable for a "live" transcript view. A lightweight in-process `asyncio.Queue` can fan-out critical status events (stage changes, errors) in parallel for low-latency UI updates without adding a Redis dependency.

**Decision impact:** Determines whether a session in progress can be resumed from a Web UI refresh, and whether the Web UI can provide a live transcript stream during a 3-hour session without risking data corruption if the web server process is restarted.

**Open sub-questions:**
- FastAPI and the bot process may need to run in the same process (for simplicity) or as separate services (for resilience). If separate, SQLite WAL is the only approach that doesn't require an IPC channel. Settle the process topology question first.
- `asyncio.to_thread` for Whisper inference blocks the thread pool. Measure whether a 5-minute chunk transcription (≈ 40 s on i7-12700K) starves the FastAPI event loop when the thread pool is at capacity.

---

## Phase 2 — Hardware Capture & Speaker Identity

### Q3 — How to achieve cross-platform audio loopback without requiring administrative virtual drivers? 🔬

**Milestone:** v1.3

**Context:** Unlike Discord, which delivers clean per-user PCM frames, desktop loopback capture introduces platform-specific complexity. WASAPI loopback is available natively on Windows with no driver installation. macOS requires a third-party virtual device (BlackHole, Loopback, Soundflower). Linux PipeWire/PulseAudio exposes monitor sources natively. Buffer settings and latency parameters vary enough between platforms that a naïve implementation produces late starts or audio dropouts.

**Query:** Evaluate `sounddevice` (PortAudio) vs. `pyaudio` for capturing system output across Windows WASAPI, macOS CoreAudio/BlackHole, and Linux PipeWire, with a focus on stability and obtaining a clean 16 kHz mono stream suitable for Whisper.

**Platform matrix:**

| Platform | Native loopback? | Required driver | `sounddevice` support | `pyaudio` support |
|----------|-----------------|-----------------|----------------------|------------------|
| Windows 10/11 (WASAPI) | ✅ Yes | None | ✅ via `wasapi_exclusive=False` | ✅ via `paWASAPI` |
| macOS 12+ (CoreAudio) | ❌ No | BlackHole (free, open-source) | ✅ after BlackHole install | ✅ after BlackHole install |
| Linux PulseAudio | ✅ Yes | None — `monitor` source | ✅ | ✅ |
| Linux PipeWire | ✅ Yes | None — virtual sink monitor | ✅ | 💭 May require `pw-jack` |

**Hypothesis:** Using `sounddevice` with `latency='low'` (PortAudio chooses the optimal block size for the platform) rather than a fixed `blocksize` provides the most stable capture. A fixed block size risks buffer underruns on PipeWire and WASAPI due to their different internal scheduling. The stream callback should write to a `queue.Queue` consumed by the chunking loop, decoupling capture latency from processing latency.

**Key experiment:** On each platform, capture 10 minutes of loopback audio, then transcribe with faster-whisper `small` int8 and compare WER to the same audio captured via Discord. Quantify any cut-off at the start of capture (PortAudio buffer warm-up) and measure it.

**Decision impact:** Determines whether macOS users must install BlackHole (a user-friction point) or if a pure `CoreAudio` API approach can be documented. Also determines whether `pyaudio` can be dropped in favour of `sounddevice` only (reducing the dependency surface).

**See also:** [deferred D3](#d3--macos-tcc-permission-strings-for-microphone-and-screen-audio-capture) for macOS TCC permission requirements when bundling.

---

### Q4 — What is the accuracy and resource floor for local speaker diarization on 8 GB RAM systems? 🔬

**Milestone:** v1.3

**Context:** For Discord sessions, speaker attribution is free — `sink.audio_data` keys are Discord `user_id` values. For standalone mic/loopback capture, RPG Watcher loses this advantage and must determine who is speaking from acoustic features alone. This is a fundamentally different and harder problem. The question is whether a diarization library can run alongside faster-whisper on a constrained 8 GB system without unacceptable latency or RAM pressure.

**Query:** Measure WER delta and peak RAM overhead when adding a speaker diarization stage to the faster-whisper pipeline, comparing `pyannote-audio 3.x` against `tinydiarize` (the embedded diarization model in faster-whisper).

**Candidates:**

| Library | Mechanism | Licence | RAM (est.) | Notes |
|---------|-----------|---------|-----------|-------|
| `pyannote-audio 3.x` | Transformer-based speaker segmentation + embedding | MIT (models: HuggingFace gated) | ~1–2 GB | HuggingFace token required for model download; model access must be accepted per user |
| `tinydiarize` | Tiny Whisper fine-tune; integrated into faster-whisper | MIT | ~100 MB extra | No separate download; speaker count must be specified; accuracy lower than pyannote |
| `SpeechBrain ECAPA-TDNN` | Speaker embedding only (no segmentation); compare against enrolled profiles | Apache 2.0 | ~200 MB | Requires VAD pre-segmentation (already have Silero); good fit for enrollment flow |
| `simple-diarizer` | Clustering on SpeechBrain embeddings, no segmentation model | MIT | ~300 MB | Lighter than pyannote; less accurate on overlapping speech |

**Key experiment:**
1. Baseline: transcribe a 60-minute test session (Discord WAV, known ground-truth speaker labels) with faster-whisper `small` int8. Record RAM and elapsed time.
2. Add each diarization candidate. Measure: (a) peak RAM delta, (b) elapsed time delta, (c) diarization error rate (DER) against ground truth labels, (d) WER change (diarization boundaries may split a sentence mid-word, degrading the transcript fed to the LLM).

**Decision impact:** If `pyannote` RAM delta pushes total usage above 8 GB on a typical system, it must be made an optional "enhanced" dependency. If `tinydiarize` DER is acceptable (< 15% for 2–6 speakers), it becomes the default with no additional download. If both are insufficient, the Voice Profile Enrollment flow (US-112) using `SpeechBrain ECAPA-TDNN` becomes mandatory for standalone users — diarization is replaced by enrollment-based attribution.

**Related:** [whisper-backends.md — Phase 3: Voice Profile Enrollment](whisper-backends.md#phase-3--voice-profile-enrollment-v05)

---

## Phase 3 — Integration & Ecosystem Portability

### Q5 — Can local-first OAuth2 flows be implemented for Notion and Google Docs without a central proxy server? 💭

**Milestone:** v1.4

**Context:** Notion and Google Docs APIs require OAuth2. The standard flow redirects the user's browser to an external authorization server, then redirects back to a `redirect_uri`. Hosted web apps use their own servers as the redirect target. Standalone local apps must receive the authorization code at `localhost`. Hosting a central "Watcher Cloud" redirect proxy violates the privacy-first principle.

**Query:** Investigate the "loopback IP address" OAuth2 flow (RFC 8252 §8.3) for receiving API tokens directly at `localhost:7432/oauth/callback` from both the Notion API and Google OAuth2.

**Hypothesis:** Both APIs support `http://localhost` as a valid `redirect_uri` for "desktop application" OAuth2 client types. A built-in FastAPI endpoint (`GET /oauth/callback?code=...&state=...`) can act as the redirect URI. The flow:
1. User clicks "Connect Notion" in the Web UI settings
2. RPG Watcher opens the Notion OAuth2 authorization URL in the user's default browser with `redirect_uri=http://localhost:7432/oauth/callback`
3. User approves in browser; Notion redirects to `localhost:7432/oauth/callback?code=...`
4. FastAPI handler exchanges the code for an access token using the user's own Notion integration client credentials
5. Token is stored in the local SQLite database (encrypted with a key derived from a user-set passphrase or the machine's hardware ID)

**Key verification steps:**
- Confirm Notion Developer API accepts `http://localhost:{dynamic_port}` as a redirect URI (some APIs require pre-registration of the exact port)
- Confirm Google OAuth2 "desktop app" client type allows `localhost` redirect without a server-side secret (PKCE flow for public clients)
- Determine whether tokens need refresh-token rotation and whether the FastAPI handler can manage this transparently

**Decision impact:** If either API does not support localhost redirect URIs, the only privacy-preserving alternative is a "manual token paste" flow (user visits developer portal, copies a token, pastes into settings). This is more friction but still fully local. The decision determines UX for the Notion and Google Docs output adapters (US-116).

---

### Q6 — What is the most resilient mixing algorithm for N-track 16-bit PCM in Python? 🔬

**Milestone:** v0.3 (for the mixer fix) / v1.3 (for the standalone master-mix archive feature)

**Context:** The current `merge_audio_data` in `src/recorder.py` uses a clamp mixer (`max(-32768, min(32767, sum(...)))`). For 3+ simultaneous speakers this produces hard-clipping distortion. There are several well-known alternatives with different trade-offs. A "master mix" WAV for session archiving requires the best possible quality, not just something Whisper can tolerate. See [discord-voice.md Q8](discord-voice.md#q8--what-is-the-audible-quality-of-the-mixed-wav-for-a-typical-4-person-session) for the original Discord-side analysis.

**Query:** Compare the following mixing algorithms on a synthetic 4-track 16-bit PCM test signal (each track at −3 dBFS; mixed simultaneously):

| Algorithm | Formula | Expected behaviour |
|-----------|---------|-------------------|
| **Clamp (current)** | `clamp(Σ samples)` | Hard clips at ±32767; distorts for 3+ speakers |
| **Linear average** | `Σ samples / N` | No clipping; volume drops 6dB per doubling of speakers |
| **Weighted average** | `Σ (sample × weight) / Σ weights` | Allows per-user volume normalisation before mixing |
| **Viktor Toth's algorithm** | `a + b - (a*b)/32768` for 2 tracks; recursive for N | No clipping; slight volume drop; perceptually transparent for speech |
| **Floating-point normalise** | Convert to float32 → sum → peak-normalise → convert back | Best quality; requires `numpy`; adds a dependency |

**Viktor Toth's algorithm** is specifically designed for 16-bit audio mixing without clipping and without the volume loss of averaging. It is used in many telephony mixing implementations. For N tracks it is applied recursively: `mix(a, b, c) = mix(mix(a, b), c)`.

**Key measurements:**
- Peak THD+N (Total Harmonic Distortion + Noise) for each algorithm with 4 simultaneous −3 dBFS tones
- CPU time for 10 minutes of 4-track 48 kHz stereo (the Discord mix format) — determines whether `numpy` is required for real-time mixing
- Perceptual test: does the Whisper `small` model WER change when fed a Viktor Toth-mixed WAV vs. the clamp-mixed WAV for the same 4-speaker test signal?

**Decision impact (two outcomes):**
1. **v0.3 (Discord bot):** Replace the clamp mixer in `merge_audio_data` with the Viktor Toth algorithm or weighted average. No new dependency if implemented in pure Python.
2. **v1.3 (standalone archive):** The master-mix WAV uses the floating-point normalise approach (with `numpy`, already a transient dependency of faster-whisper) for best archival quality.

---

## Phase 4 — Packaging & Distribution

### Q7 — What is the minimum viable bundle size for a standalone installer including Python, faster-whisper, and a 4-bit LLM? 🔬

**Milestone:** v2.0

**Context:** A standalone installer must bundle the Python runtime and all dependencies, but Whisper models (75 MB – 3.1 GB) and Ollama LLM models (4–10 GB) make "bundle everything" impractical. The question is where to draw the line between what ships in the installer and what is downloaded on first run.

**Query:** Test executable compression using PyInstaller and Briefcase for a bundle containing `faster-whisper` and its CTranslate2/MKL/CUDA dependencies. Measure compressed installer size and first-run model download size for the recommended configuration (`small` Whisper model + `llama3.1:8b` Q4).

**Proposed split:**

| Component | Bundle in installer? | Reason |
|-----------|---------------------|--------|
| Python 3.11 runtime | ✅ Yes | ~30 MB compressed; eliminates Python version friction |
| `faster-whisper` library | ✅ Yes | ~50 MB with CTranslate2; small enough to bundle |
| `tiny` Whisper GGML model | ✅ Yes | 32 MB; enables a working demo/test on first run |
| `small` Whisper GGML model | ❌ Download on first run | 190 MB; post-install first-run wizard (US-120) |
| Ollama binary | ✅ Yes (or detect existing) | ~15 MB on Windows; eliminates separate Ollama install |
| `llama3.1:8b` Q4 model | ❌ Download on first run | 4.7 GB; cannot bundle; first-run wizard step |
| Web UI (HTML/CSS/JS) | ✅ Yes | < 5 MB; must be immediately available |

**Target installer size:** < 150 MB download → < 500 MB on disk before model downloads.

**Key experiments:**
- PyInstaller `--onedir` vs. `--onefile` for a `faster-whisper` bundle: `--onefile` is convenient but slower to start (full extract on each launch); `--onedir` starts faster but is less tidy
- Measure startup time: time from double-click to Web UI available in browser, for both strategies
- Briefcase produces platform-native packages (`.msi`, `.pkg`, `.deb`) with proper uninstallers; compare against PyInstaller `.exe` + NSIS for Windows

**Decision impact:** Determines first-run UX. A 150 MB installer with a post-install download wizard (US-120) is the target. If the bundle cannot be kept under 200 MB, the `tiny` Whisper model must also be post-install.

**See also:** [deferred D1](#d1--vulkan-backend-for-whisper-in-a-bundled-environment) — Vulkan support could make the `small` model as fast as `tiny` on most modern GPUs, making the `small` model the right first-run default.

---

### Q8 — How to manage `num_ctx` dynamically in a standalone app to prevent model amnesia? 🔬

**Milestone:** v1.2 (detection + warning) / v2.0 (adaptive context management)

**Context:** Ollama defaults `num_ctx` to 2 048 tokens regardless of the model's architectural maximum. This is separate from and more damaging than the model's published context window: even `llama3.1` (128k architectural limit) will truncate at 2 048 tokens under Ollama's default. The fix for the bot (`OLLAMA_MODEL=llama3.1` + explicit `num_ctx` in the API call) must become automatic and adaptive in the standalone application.

**Note:** The `mistral` 8 192-token architectural limit and the recommended migration to `llama3.1` are documented in [llm-models.md Q8](llm-models.md#context-window--truncation--critical-analysis--answered-by-arithmetic). This query addresses the layer below that: ensuring Ollama's *runtime* context window matches the model's *architectural* capability.

**Query:** Implement "Adaptive Context" logic that: (1) detects the architectural `num_ctx` limit for the active model by querying `ollama show <model>`, (2) estimates the token count of the current transcript before the API call, (3) sets `num_ctx` in the `options` dict to the minimum of the model's architectural limit and `max(estimated_tokens * 1.25, 4096)`.

**Proposed implementation:**

```python
import subprocess, json, math

def get_model_context_limit(model: str) -> int:
    """Query Ollama for the model's architectural num_ctx limit."""
    result = subprocess.run(
        ["ollama", "show", "--modelfile", model],
        capture_output=True, text=True
    )
    for line in result.stdout.splitlines():
        if "num_ctx" in line:
            return int(line.split()[-1])
    return 4096  # safe fallback

def estimate_tokens(text: str) -> int:
    """Fast approximation: 1 token ≈ 4 characters for English text."""
    return math.ceil(len(text) / 4)

def build_ollama_options(transcript: str, model: str) -> dict:
    model_limit = get_model_context_limit(model)
    transcript_tokens = estimate_tokens(transcript)
    # Add 20% headroom for system prompt + output tokens
    required_ctx = min(model_limit, max(int(transcript_tokens * 1.25), 4096))
    return {
        "num_ctx": required_ctx,
        "temperature": 0,
    }
```

**Decision impact:** Without this, the standalone app silently truncates every transcript longer than ~8 000 characters (≈ 2 048 tokens × 4 chars/token) regardless of which model is configured. This would produce broken session notes on even 30-minute sessions. This logic must land in v1.2 alongside the Web UI (where the token count and context usage can be surfaced as a progress indicator).

**Open sub-questions:**
- `ollama show --modelfile` parses a Modelfile; the `num_ctx` parameter may not always be present (it inherits from the base model). Need a fallback table of known model architectural limits.
- Token estimation via character count is fast but imprecise. For TTRPG transcripts with many fantasy proper nouns, the 4-char/token ratio may be too aggressive. Measure against `tiktoken` (OpenAI tokenizer) on a real 3-hour transcript.

---

## Deferred Queries

### D1 — Vulkan backend for Whisper in a bundled environment 💭

**Target milestone:** v2.0

Whisper.cpp 1.8.x includes a Vulkan compute backend that provides GPU acceleration on any Vulkan 1.2-capable GPU, including integrated Intel/AMD GPUs that lack CUDA. Benchmarks from the whisper.cpp project suggest 8–15× speedup over CPU for `small` model inference using Vulkan on a mid-range discrete GPU.

**Query:** Can the Vulkan backend be compiled into a `whisper.cpp` binary bundled within a PyInstaller/Briefcase package, and does it function correctly without requiring a separate Vulkan SDK installation from the end user?

**Decision impact:** If Vulkan can ship bundled, the `small` model becomes fast enough to be the default first-run choice (replacing `tiny`), dramatically improving transcription quality for the average standalone user. This would also be a strong marketing differentiator — "GPU-accelerated transcription on any machine, no CUDA required."

---

### D2 — Secure auto-update via GitHub Releases 💭

**Target milestone:** v2.0

**Query:** How to implement a signature-verified auto-update mechanism using only GitHub Releases and local Python scripts, without relying on a central update server?

**Proposed approach:** GitHub Releases publishes a `checksums.sha256` file signed with the project's GPG/Sigstore key alongside each release asset. The auto-updater:
1. Fetches the GitHub Releases API to check the latest version tag
2. Downloads the signature file for the new release
3. Verifies the signature against the project's public key (bundled in the installer)
4. Only if verification passes: downloads and applies the update

**Decision impact:** Determines whether auto-update (US-123) can be implemented safely without introducing a dynamic code-execution attack surface. Sigstore's `cosign` may be preferable to GPG for a Python project already on PyPI.

---

### D3 — macOS TCC permission strings for microphone and screen audio capture 💭

**Target milestone:** v2.0

**Query:** What are the specific `NSMicrophoneUsageDescription`, `NSScreenCaptureUsageDescription` (and any related `com.apple.security.device.audio-input` entitlement) strings required in a bundled macOS `.app` for system microphone access and system audio capture (via BlackHole or ScreenCaptureKit)?

**Context:** macOS Transparency, Consent, and Control (TCC) denies microphone access to any process that does not declare the correct `Info.plist` keys. PyInstaller and Briefcase generate these automatically for known permissions but may miss less-common entitlements required for audio loopback capture.

**Decision impact:** Determines whether the macOS installer can be built without a paid Apple Developer Programme membership (required for notarization). An unsigned `.app` triggers Gatekeeper on Apple Silicon Macs; users must right-click → Open on first launch. The friction of this vs. the cost of notarization is a packaging decision for v2.0.

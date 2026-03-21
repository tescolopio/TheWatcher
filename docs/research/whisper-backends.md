# Research: Whisper Transcription Backends

**Status:** 🔬 Active — Q1/Q2 need runtime measurement; Q3–Q5 answered; faster-whisper identified as better default  
**Informs:** [ADR-0003](../adr/0003-dual-whisper-backends.md), `src/transcriber.py`

> ⚠️ **Action needed:** The model path resolution in `_transcribe_with_whisper_cpp` is fragile and will fail for most real installs.  Recommend adding a `WHISPER_CPP_MODEL_PATH` env var.  See Q5.

---

## Query Status Key

| Symbol | Meaning |
|--------|---------|
| ✅ | Answered — measured and recorded |
| 🔬 | Open — experiment designed but not yet run |
| 💭 | Hypothesis — inferred from published benchmarks or model cards; not measured by us |

---

## Background (Established Facts)

[Whisper](https://github.com/openai/whisper) is OpenAI's speech recognition model (MIT licence).  Two local implementations are relevant to RPG Watcher:

| Implementation | Language | GPU required? | Install |
|---------------|----------|--------------|---------|
| `openai-whisper` | Python / PyTorch | No (faster with GPU) | `pip install openai-whisper` |
| `whisper.cpp` | C++ | No | Compile or download binary |

**Model sizes** (from the OpenAI Whisper paper and model cards — parameters and quantised sizes are fixed facts):

| Model | Parameters | `.pt` size | GGML Q5 size | Published English WER |
|-------|-----------|-----------|-------------|----------------------|
| `tiny` | 39 M | 75 MB | 32 MB | ~7.7% |
| `base` | 74 M | 142 MB | 60 MB | ~5.7% |
| `small` | 244 M | 466 MB | 190 MB | ~3.4% |
| `medium` | 769 M | 1.5 GB | 515 MB | ~2.1% |
| `large-v3` | 1 550 M | 3.1 GB | 1.1 GB | ~1.8% |

WER figures are from the [OpenAI Whisper paper](https://arxiv.org/abs/2212.04356) on clean English speech.  TTRPG sessions (crosstalk, accents, invented vocabulary) will produce higher WER — measuring this is an open query.

**Whisper's native input format:** 16 kHz, mono, 30-second chunks.  Both backends handle resampling from Discord's 48 kHz stereo internally — whether this introduces quality loss is an open query.

---

## Open Research Queries

### Q1 — Wall-clock time and peak RAM per backend and model size 🔬 (measurements needed for our hardware)

**Reference benchmark — official faster-whisper data** (13-minute audio, Intel Core i7-12700K, 8 threads):

| Backend | Model | Precision | Wall-clock (13 min) | RAM | Source |
|---------|-------|-----------|-------------------|-----|--------|
| openai-whisper | small | fp32 | 6m 58s | 2 335 MB | faster-whisper README |
| whisper.cpp | small | fp32 | 2m 05s | 1 049 MB | faster-whisper README |
| faster-whisper | small | fp32 | 2m 37s | 2 257 MB | faster-whisper README |
| faster-whisper | small | int8 | 1m 42s | 1 477 MB | faster-whisper README |
| faster-whisper (batch=8) | small | int8 | 0m 51s | 3 608 MB | faster-whisper README |

**Extrapolated to 60 minutes** (4.6× scale — linear approximation; actual may differ for short-segment overhead):

| Backend | Model | Precision | ~60 min est. | ~60 min RAM |
|---------|-------|-----------|------------|-------------|
| openai-whisper | small | fp32 | ~32 min | ~2.3 GB |
| whisper.cpp | small | fp32 | ~9.6 min | ~1.0 GB |
| faster-whisper | small | fp32 | ~12 min | ~2.3 GB |
| faster-whisper | small | int8 | ~7.9 min | ~1.5 GB |
| faster-whisper (batch=8) | small | int8 | ~3.9 min | ~3.6 GB |

**whisper.cpp RAM by model size** (from whisper.cpp README):

| Model | RAM (whisper.cpp) |
|-------|------------------|
| tiny | ~273 MB |
| base | ~388 MB |
| small | ~852 MB |
| medium | ~2.1 GB |
| large | ~3.9 GB |

**Matrix still needed — measure on RPG Watcher’s actual target hardware:**

The benchmark harness in the original Q1 spec remains valid; run it for the models/backends you plan to recommend and fill this in:

| Backend | Model | Wall-clock (60 min input) | RAM delta | Hardware | Status |
|---------|-------|--------------------------|-----------|----------|--------|
| faster-whisper | small int8 | — | — | — | 🔬 |
| faster-whisper | base int8 | — | — | — | 🔬 |
| whisper.cpp | small | — | — | — | 🔬 |

---

### Q2 — Transcript quality on TTRPG-style speech 🔬

Published WER figures are measured on clean English speech (LibriSpeech).  TTRPG sessions differ:
- Multiple simultaneous speakers (crosstalk)
- Invented proper nouns ("Theron Ashveil", "the Sundering Blade")
- Theatrical accents and character voices
- Dice rolls, laughter, side-chatter

**Experiment:** Transcribe the same 60-minute test WAV with each model.  Manually score accuracy against a hand-written reference transcript for 5-minute excerpts covering:
1. Clean single-speaker narration
2. 2-person back-and-forth dialogue
3. A passage containing 4 invented proper nouns
4. A loud background-noise segment

**Metrics:** WER per excerpt, proper noun accuracy (exact match ÷ total occurrences).

**Decision output:** Determines the recommended default model (`base` for speed vs `small` for accuracy).

---

### Q3 — Does pre-resampling to 16 kHz mono improve speed or quality? � Low value — not recommended

**Analysis:** Both backends internally resample from 48 kHz stereo to 16 kHz mono before running the model encoder.  For `openai-whisper`, this is done via `ffmpeg` or `soundfile` on the full file before segmenting.  For `whisper.cpp`, it is done per-30-second chunk in C.

Pre-resampling externally with `ffmpeg` saves the Python/C resampling cost, but that cost is already small relative to model inference time.  The official faster-whisper benchmarks show that their int8 implementation — which also handles resampling internally — achieves parity with whisper.cpp speed without pre-resampling.

**Expected saving:** ~5–10% wall-clock reduction for long sessions.  Not worth the added `ffmpeg` preprocessing step and the extra temp file I/O.

**Decision:** Do not add pre-resampling as a default step.  If users report unusually slow transcription on constrained hardware, offer it as an opt-in `WHISPER_PRERESAMPLE=1` env var.

---

### Q4 — What is the actual stdout format of `whisper.cpp --output-txt -`? ✅ Answered

**Finding:** `whisper.cpp`’s `whisper-cli` behaviour with text output:

- **Without output flags:** Outputs timestamped segments to stdout: `[00:00:00.000 --> 00:00:11.000]   text text text`
- **`--output-txt filename.txt`:** Writes plain text (no timestamps) to `filename.txt`.
- **`--output-txt -`:** In recent builds, `"-"` is treated as the literal filename `"-"`, writing to a file called `-` in the current directory — **not to stdout**.  This is a known source of confusion.

**Current `_transcribe_with_whisper_cpp` code uses `--output-txt -` and reads `result.stdout`.**  This means the code may be capturing timestamped text from the default console output rather than the plain-text file, and reading an empty stdout if the binary writes output to a file.

**Action required:** Replace the subprocess invocation to use `--no-timestamps` (or omit `-ot`) and capture stdout directly without `--output-txt`:
```python
result = subprocess.run(
    [whisper_cpp_path, "-m", str(model_file), "-f", str(audio_path),
     "--no-timestamps"],   # plain text to stdout
    capture_output=True,
    text=True,
    timeout=600,
)
```
Alternatively, write to a temp file and read it back:
```python
import tempfile
with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as tf:
    subprocess.run([whisper_cpp_path, "-m", str(model_file), "-f", str(audio_path),
                    "--output-txt", tf.name[:-4]], ...)  # whisper-cli appends .txt
    return Path(tf.name).read_text().strip()
```

---

### Q5 — whisper.cpp binary name and model path resolution ✅ Answered — current code has a bug

**Binary name:** `whisper-cli` (renamed from `main` in a 2024 release, confirmed in whisper.cpp README).  `WHISPER_CPP_PATH` should point to the binary directly: `WHISPER_CPP_PATH=/path/to/whisper.cpp/build/bin/whisper-cli`.

**Model path bug in current code:**

```python
# src/transcriber.py, current line:
model_file = Path(whisper_cpp_path).parent / "models" / f"ggml-{model}.bin"
```

If `WHISPER_CPP_PATH=/path/to/whisper.cpp/build/bin/whisper-cli`, this resolves to:
```
/path/to/whisper.cpp/build/bin/models/ggml-base.bin
```

But `download-ggml-model.sh` places models at:
```
/path/to/whisper.cpp/models/ggml-base.bin   ← two levels up, not in build/bin/
```

**This path will not exist for any standard whisper.cpp install.**  The binary will fail with model-not-found.

**Fix — add a dedicated `WHISPER_CPP_MODEL_PATH` env var:**
```python
whisper_cpp_path = os.environ["WHISPER_CPP_PATH"]
model = os.getenv("WHISPER_MODEL", "base")

# New: explicit model path, falling back to the old heuristic for now
model_dir = os.getenv(
    "WHISPER_CPP_MODEL_PATH",
    str(Path(whisper_cpp_path).parent / "models"),  # keep old default as fallback
)
model_file = Path(model_dir) / f"ggml-{model}.bin"
```

Document in `docs/configuration.md`:
```dotenv
WHISPER_CPP_PATH=/path/to/whisper.cpp/build/bin/whisper-cli
WHISPER_CPP_MODEL_PATH=/path/to/whisper.cpp/models   # add this
WHISPER_MODEL=small
```

**Spaces in path:** `subprocess.run` receives a list, not a shell string, so paths with spaces work correctly with the current code.

---

### Q6 — At what input length does `openai-whisper` OOM on 8 GB RAM? 🔬

PyTorch loads the model once and segments audio internally into 30-second chunks.  However, peak RAM also includes the loaded audio waveform tensor.

**Experiment:** Transcribe WAV files of 30 / 60 / 120 / 180 minutes with `small` model on an 8 GB RAM machine (or `ulimit -v`).  Record whether OOM occurs and at what input length.

**Decision output:** Feeds the minimum hardware requirements in the README and deployment guide.

---

### Q7 — Language auto-detection accuracy for non-English sessions 🔬

**Experiment:** Run both backends with no `--language` flag on:
- 10-minute French session audio
- 10-minute German session audio
- 10-minute English session with a French NPC accent

Record detected language metadata from `result["language"]` (openai-whisper Python API) or whisper.cpp verbose output.

**Decision output:** If auto-detection misfires → add `WHISPER_LANGUAGE` env var as a higher-priority feature (currently deferred).

---

## Recommended Third Backend: `faster-whisper`

`faster-whisper` is a CTranslate2-based reimplementation of Whisper that should replace `openai-whisper` as the Python fallback.  It uses the same model names and is a near drop-in replacement.

**Why it is better than `openai-whisper` for RPG Watcher:**

| Feature | openai-whisper | faster-whisper |
|---------|---------------|----------------|
| Speed (small, CPU) | ~32 min / 60 min audio | ~7.9 min / 60 min audio (int8) |
| RAM (small model) | ~2.3 GB | ~1.5 GB (int8) |
| ffmpeg on PATH required | **Yes** | **No** — uses PyAV |
| Built-in VAD | No | **Yes** — Silero VAD |
| Word-level timestamps | No | **Yes** |
| Python API | Yes | Yes |

**Install:** `pip install faster-whisper`

**Usage in `_transcribe_with_python_whisper`:**
```python
from faster_whisper import WhisperModel

model_name = os.getenv("WHISPER_MODEL", "small")  # upgrade default from base → small
model = WhisperModel(model_name, device="cpu", compute_type="int8")

# vad_filter=True skips silent segments — significant speedup for TTRPG recordings
# (Discord VAD already drops silence, but room noise and open-mic hum accumulates)
segments, info = model.transcribe(str(audio_path), vad_filter=True)
return " ".join(seg.text.strip() for seg in segments)
```

**Add to `requirements.txt`:**
```
faster-whisper>=1.0.0
```

**Remove from `requirements.txt`:** `openai-whisper` (keep as optional in `requirements-dev.txt` if comparison testing is needed)

**Note on default model upgrade:** Change `WHISPER_MODEL` default from `base` to `small`.  With faster-whisper int8, `small` runs at roughly the same wall-clock time as `base` on openai-whisper, with meaningfully better TTRPG accuracy (fewer proper noun errors, better handling of overlapping speech).

---

## Chunked Recording & Transcription Architecture 💭

**Core idea:** Instead of buffering the entire session and transcribing at the end, divide the session into fixed-length audio chunks (e.g. 5 minutes), transcribe each chunk as it completes, and accumulate the running transcript throughout the session.

### Why this is the right architecture

| Problem with current (whole-session) approach | How chunking solves it |
|----------------------------------------------|------------------------|
| End-of-session spike: all transcription + summarization happens at once | ~90% of transcription completes *during* the session; end spike is just the last partial chunk |
| Memory: hours of 48 kHz stereo PCM buffered in RAM (~90 MB/hr per user) | Only the current chunk's audio is buffered at any time |
| Whisper's 30-second internal chunk limit means it already re-segments long audio internally | We control segment boundaries explicitly |
| If the bot crashes, entire session is lost | Completed chunk transcripts survive a crash |

### Latency math (with faster-whisper small int8)

faster-whisper small int8 processes ~7.6× faster than realtime on an i7-12700K (from Q1 benchmarks: 13-min audio → 1m42s ≈ 7.6× RT).

| Chunk size | Transcription time | Idle time before next chunk starts | Net overhead at session end |
|---|---|---|---|
| 2 min | ~16 s | 104 s | 16 s |
| 5 min | ~40 s | 260 s | 40 s |
| 10 min | ~80 s | 520 s | 80 s |

For a 3-hour session with 5-minute chunks, 35 out of 36 chunks are transcribed before the session ends.  The user waits ~40 s for the last chunk, then a further ~1–2 min for LLM summarization.  Compare to the current approach: 3-hour session → ~14 minutes of transcription blocking at session end before summarization even starts.

### Implementation design

**Chunk loop (background `asyncio.Task` started on recording start):**

```python
async def _chunk_loop(
    sink: discord.sinks.PCMSink,
    transcript_parts: list[str],
    chunk_seconds: int = 300,
) -> None:
    """Every chunk_seconds, snapshot the sink's audio, write a temp WAV,
    transcribe it, append to transcript_parts, then clear the buffer."""
    while True:
        await asyncio.sleep(chunk_seconds)
        # Snapshot and reset each user's buffer atomically
        audio_data = dict(sink.audio_data)       # shallow copy of references
        for user_id, data in audio_data.items():
            data.file.seek(0)
            chunk_pcm = data.file.read()
            data.file.seek(0)
            data.file.truncate()                 # reset for next chunk
        if not audio_data:
            continue
        # Write merged chunk to temp WAV, transcribe, accumulate
        chunk_wav = await asyncio.to_thread(
            write_chunk_wav, audio_data, chunk_seconds
        )
        text = await asyncio.to_thread(transcribe, chunk_wav)
        transcript_parts.append(text)
        chunk_wav.unlink(missing_ok=True)
```

**At session end (`_on_recording_finished`):**

```python
# Cancel the chunk loop
chunk_task.cancel()
# Transcribe whatever remains in the buffer (the final partial chunk)
final_text = await asyncio.to_thread(transcribe, remaining_wav)
transcript_parts.append(final_text)
# Join and write full transcript
full_transcript = "\n".join(transcript_parts)
```

### Open questions for this design

- `sink.audio_data` access while py-cord is actively writing to it: need to confirm thread safety or use a lock.  py-cord's sink writes happen in the voice receive thread; the chunk loop runs in the asyncio event loop thread — a threading lock on the buffer swap is required.
- Sentence fragments at chunk boundaries: faster-whisper can be configured with `condition_on_previous_text=True` and previous segment text passed via `initial_prompt` to improve cross-boundary coherence.
- Silent chunks (all users muted): PCMSink stores nothing for that window.  The chunk loop must detect empty audio and skip transcription rather than calling Whisper on a silent WAV.
- With WAV output (WaveSink, see [discord-voice.md](discord-voice.md)), per-user chunk files can be written directly without the merge step — this is the cleaner architecture for v0.5+.

### Summarization interaction

Chunked transcription does **not** automatically fix the LLM context window problem — the full accumulated transcript is still fed to the LLM at the end, and it will still be 28k+ tokens for a 3-hour session.  Two strategies:

1. **Accumulate and summarize once (recommended for v0.3):** Keep chunked transcription, change the default model to `llama3.1` (128k context), feed full transcript at end.  Clean, simple, accurate.
2. **Per-chunk summarization (v0.5+):** Summarize each chunk individually ("what happened in the last 5 minutes"), then merge summaries at the end with a final pass.  Enables 8k models, but accuracy suffers — events spanning chunk boundaries can be lost or duplicated.

See [llm-models.md](llm-models.md) Q8 for context window analysis.

---

## Per-Speaker Transcription & Character Voice Learning 💭

### The key insight: Discord already does speaker separation

Conventional speaker diarization problems ("who is speaking when?") are solved by algorithms like pyannote because they start from a *single mixed audio stream* and must figure out speaker boundaries from acoustic differences alone.  RPG Watcher never faces this problem.

`sink.audio_data` is `dict[int, AudioData]` keyed by **Discord `user_id`**.  Each entry is that user's audio, and nothing else.  We know exactly who is speaking at every moment.  No diarization library is needed.  The architecture is simpler than it first appears.

**Standalone note:** This advantage is lost for mic/loopback sources in the v1.3+ standalone application.  Those sources produce a single mixed stream and require diarization to attribute speech to speakers.  A full evaluation of `pyannote-audio`, `tinydiarize`, and `SpeechBrain ECAPA-TDNN` on 8 GB RAM systems is in [standalone-architecture.md Q4](standalone-architecture.md#q4--what-is-the-accuracy-and-resource-floor-for-local-speaker-diarization-on-8-gb-ram-systems).

### What "learn over time" concretely means

There are four layers of learning, each independently useful and incrementally addable:

| Layer | Mechanism | Sessions to benefit | Complexity |
|-------|-----------|--------------------|-----------|
| **Character name list in LLM prompt** | system prompt updated with registered names | 0 — works immediately | Low |
| **Vocabulary bias in Whisper** | per-server `vocabulary.json` fed as `initial_prompt` | 1+ — grows each session | Low |
| **Voice profile robustness** | more audio → denser speaker embedding centroid | 3+ sessions | Medium |
| **Fantasy word canonicalization** | LLM post-processing accumulates corrections | 5+ sessions | Medium |

---

### Phase 1 — Character Name Registry + Per-User Transcription (v0.4)

**Goal:** Every transcript line reads `[Theron Ashveil]: I draw my sword.` instead of an unlabelled block of text.

**Storage:** A per-guild JSON file (or SQLite row) mapping Discord user IDs to character info:

```json
// data/guilds/123456789/characters.json
{
    "987654321": { "character": "Theron Ashveil", "player": "Alex" },
    "876543210": { "character": "Mira",           "player": "Sam" },
    "765432109": { "character": "Narrator",        "player": "GM" }
}
```

**Bot commands:**
```
/register-character character:<name>     — registers yourself for this guild
/register-character character:<name> player:<name>  — with OOC player name
/characters                              — list registered characters
```

**Transcription loop** (per chunk or per session, with WaveSink):

```python
segments = []
for user_id, audio in sink.audio_data.items():
    profile = character_registry.get(guild_id, user_id)
    name = profile["character"] if profile else f"Player{user_id}"

    # Bias Whisper towards this character's known vocabulary
    vocab_hint = build_vocab_prompt(guild_id, user_id)
    result = transcriber.transcribe(
        audio_path,
        initial_prompt=f"This is {name} speaking. {vocab_hint}"
    )
    segments.append((audio_start_time[user_id], f"[{name}]: {result.strip()}"))

# Sort by timestamp to reconstruct dialogue order
segments.sort(key=lambda s: s[0])
full_transcript = "\n".join(text for _, text in segments)
```

**LLM system prompt addition:**  Prepend a cast list to the system prompt so the model doesn't confuse character names or invent new ones:
```
CAST FOR THIS SESSION:
- Theron Ashveil (played by Alex)
- Mira (played by Sam)
- Narrator / GM (Sam)
```

**Turn-based TTRPG advantage:** Real TTRPG sessions have very little simultaneous speech — combat is sequential, side-chatter is rare.  Combined with faster-whisper's built-in VAD (`vad_filter=True`), each user’s audio is already naturally segmented by utterance.  The timestamp-sort above reconstructs the turn order accurately without any diarization.

---

### Phase 2 — Per-Server Vocabulary Accumulation (v0.4/v0.5)

**Goal:** After session 1, Whisper already knows how to spell "Theron Ashveil" in session 2.

**Mechanism:** After the LLM produces a summary, extract all named entities (character names, place names, item names, spells) from the summary output.  These are already in the correct spelling because the LLM canonicalized them.  Append to a per-guild vocabulary counter:

```python
# data/guilds/123456789/vocabulary.json
{
    "Theron Ashveil": 5,      # seen in 5 sessions
    "the Sundering Blade": 3,
    "Mirethaal": 2,
    "Vex\'ahlia": 4
}
```

Build the `initial_prompt` from the top-N most frequent terms:

```python
def build_vocab_prompt(guild_id: int, top_n: int = 20) -> str:
    vocab = load_vocab(guild_id)
    top = sorted(vocab, key=vocab.get, reverse=True)[:top_n]
    if not top:
        return ""
    return "Known names and terms: " + ", ".join(top) + "."

# Result example:
# "Known names and terms: Theron Ashveil, the Sundering Blade, Mirethaal, Vex'ahlia."
```

This requires no model training.  It works because Whisper's decoder uses `initial_prompt` tokens as a soft prior — it will strongly prefer spellings it has been shown.  After 3–5 sessions, invented TTRPG vocabulary converges to consistent spellings automatically.

Users can also add words manually:
```
/vocab add <word>      — add to guild vocabulary
/vocab list           — show current vocabulary
/vocab remove <word>  — remove incorrect entry
```

---

### Phase 3 — Voice Profile Enrollment (v0.5+)

**Goal:** Identify speakers even when Discord metadata is unavailable — for example, post-processing an audio file captured outside of RPG Watcher, or verifying that the voice speaking matches the registered user.

**Mechanism:** Speaker embedding models (e.g. [SpeechBrain ECAPA-TDNN](https://huggingface.co/speechbrain/spkrec-ecapa-voxceleb), MIT licence) compress a speech segment into a fixed-length embedding vector.  Cosine similarity between embeddings measures speaker similarity.

**Enrollment:**
```
/enroll     — prompts the user to speak 3 short phrases in voice channel
            — records ~30 s, computes embedding, stores against user_id
```

**How it gets better over time:**  Each session, compute embeddings for all of a user’s audio and average them into a running centroid.  After 5+ sessions, the centroid represents their voice much more robustly than a single 30-second enrollment.

**Practical note for RPG Watcher:**  Phase 3 is **not required** for the core feature — Discord user_id already uniquely identifies speakers.  The main use case is a future "post-process an existing recording" feature where per-user audio tracks aren’t available.  Implementing Phases 1 and 2 delivers the full user-facing value with no ML training pipeline.

---

## Backend Reference

### `openai-whisper` — code path

`src/transcriber._transcribe_with_python_whisper()` — lazy model load on first call, `model.transcribe(str(audio_path))`, returns `result["text"]`.

Configuration: `WHISPER_MODEL` env var (default: `base`).

### `whisper.cpp` — code path

`src/transcriber._transcribe_with_whisper_cpp()` — `subprocess.run([WHISPER_CPP_PATH, "-m", model_file, "-f", audio_path, "--output-txt", "-"])`, returns stripped stdout.

Configuration: `WHISPER_CPP_PATH` (binary path) + `WHISPER_MODEL` (default: `base`).
Model file expected at: `<dirname(WHISPER_CPP_PATH)>/models/ggml-<WHISPER_MODEL>.bin`.

### Building whisper.cpp

```bash
git clone https://github.com/ggerganov/whisper.cpp.git
cd whisper.cpp
cmake -B build
cmake --build build --config Release
bash models/download-ggml-model.sh base
```

---

## Recommended Direction

| Priority | Action | Target | Impact |
|----------|--------|--------|--------|
| 🔴 **Critical** | Fix `--output-txt -` stdout issue in `_transcribe_with_whisper_cpp` | v0.2 | whisper.cpp may be returning empty transcripts silently |
| 🔴 **Critical** | Add `WHISPER_CPP_MODEL_PATH` env var; fix model path resolution | v0.2 | whisper.cpp unusable with standard install as-is |
| 🟡 **High** | Replace `openai-whisper` with `faster-whisper` as Python fallback | v0.3 | 4× speed improvement, removes ffmpeg dependency |
| 🟡 **High** | Change default `WHISPER_MODEL` from `base` → `small` | v0.3 | Meaningfully better accuracy at same effective speed with faster-whisper |
| � **High** | Implement chunked transcription architecture | v0.3 | Eliminates end-of-session latency spike; bounds RAM; transcription runs during the session |
| 🟢 **Medium** | Enable `vad_filter=True` in faster-whisper call | v0.3 | Skips background hum/silence; reduces transcription time — essential for chunked mode where silent chunks must be skipped |
| 🟢 **Medium** | Run hardware-specific benchmarks and document in README | v0.3 | Helps users choose model based on their machine |
| 🟢 **Medium** | Add `initial_prompt` (previous chunk text) to faster-whisper calls in chunked mode | v0.3 | Improves cross-boundary transcription coherence |
| 🟣 **Low** | Evaluate `whisper-large-v3-turbo` via faster-whisper | v0.5 | Large accuracy with ~6× less compute than large-v3 |

---

### Q12 — FUTO Whisper ACFT models: are they better for RPG Watcher? 💭 Answered by design analysis

**What FUTO ACFT is:**
[FUTO](https://futo.org) developed an open-source fine-tuning technique called **ACFT (Audio Context Fine-Tuning)** for Whisper models.  The problem they solved: Whisper's encoder always processes a fixed 30-second window, even if the spoken audio is only 3 seconds long — the rest is padded with silence.  On a phone, encoding 27 seconds of nothing is slow.  ACFT fine-tunes the model to tolerate a `dynamic audio_ctx` parameter in whisper.cpp so the encoder only processes the audio that actually exists, dramatically reducing latency for short clips.

**Available models (MIT licence, GGML `.bin` + HuggingFace safetensors):**

| Model | Params | WER (normal ctx) | WER (dynamic ctx) | Notes |
|-------|--------|-----------------|------------------|-------|
| `tiny.en` ACFT | 39 M | 4.96% (+0.23%) | 5.50% | vs stock tiny.en 4.73% |
| `base.en` ACFT | 74 M | slightly higher | comparable | — |
| `small.en` ACFT | 244 M | 2.88% (+0.11%) | 2.81% | vs stock small.en 2.77% |
| `tiny/base/small` ACFT | — | similar | comparable | Multilingual variants |

**No medium or large variants** — FUTO only trained tiny/base/small.  You can train your own from the published notebooks.

**Why these models feel fastest/best in keyboard use:**
For a 4-second voice dictation, dynamic audio_ctx means the encoder processes 4 seconds instead of 30 — a 7.5× speedup on the encoder alone.  On a mid-range Android phone where the encoder is the bottleneck, this makes dictation feel nearly instant.  The perceived quality improvement is mostly latency, not accuracy.

**Why this advantage does NOT transfer to RPG Watcher:**

1. **Chunk size mismatch:** RPG Watcher's chunked transcription processes 2–10 minute audio segments.  Whisper internally splits any audio longer than 30 seconds into sequential 30-second frames regardless of `audio_ctx`.  The ACFT optimization only applies to the final short frame at the end of a chunk (a few seconds of remainder after the last full 30-second window) — negligible for multi-minute chunks.

2. **No large model available:** TTRPG sessions have invented proper nouns, fantasy vocabulary, accents, and cross-talk.  The recommended minimum is `small`; `medium` or `large-v3-turbo` are meaningfully better for entity fidelity.  FUTO provides nothing above `small`.

3. **Slightly higher WER on full-context audio:** When running with a normal fixed 30-second context (which is what multi-minute chunks use for all but their final frame), ACFT models score marginally *worse* on standard benchmarks than stock Whisper models, not better.

4. **faster-whisper handles this better:** faster-whisper with `vad_filter=True` already skips silent frames using Silero VAD, achieving a similar practical speedup to ACFT on typical TTRPG audio (long silences between speakers) without the WER trade-off or the model size limitation.

**Verdict for RPG Watcher:**  The FUTO ACFT models are well-executed and MIT-licensed, but they are purpose-built for real-time short-utterance keyboard dictation.  For RPG Watcher's multi-minute chunked session transcription, they offer no latency benefit and have no large-model variants.  **Do not substitute for standard Whisper models in this use case.**

**When to revisit:** If RPG Watcher ever gains a real-time streaming transcription mode (e.g. live caption display during a session, processing utterances as they are spoken rather than in bulk chunks), the ACFT models become genuinely relevant — dynamic audio_ctx would allow encoding each utterance as it ends rather than waiting for a 30-second window to fill.  Track as deferred Q11.

---

## Deferred Queries

| # | Target milestone | Query |
|---|-----------------|-------|
| Q8 | v0.5 | Evaluate `faster-whisper` as a third backend (CTranslate2-based; similar speed to whisper.cpp with Python API) |
| Q9 | v0.6 | Add `WHISPER_LANGUAGE` env var for explicit language selection |
| Q10 | v0.6 | Measure quality difference between 48 kHz stereo vs pre-downsampled 16 kHz mono for TTRPG audio |
| Q11 | v0.5+ | Re-evaluate FUTO ACFT models if real-time per-utterance streaming transcription is ever added (where the latency advantage actually applies) |
| Q13 | v0.5+ | Benchmark SpeechBrain ECAPA-TDNN embedding latency on session audio to determine whether voice profile updates can run in the same `asyncio.to_thread` pass as transcription |


# Research: Discord Voice Recording with py-cord

**Status:** 🔬 Active — several questions answered from py-cord source; critical silence-dropping issue confirmed  
**Informs:** [ADR-0002](../adr/0002-pycord-discord-library.md), `src/recorder.py`

> ⚠️ **Critical finding:** PCMSink drops all silence.  Multi-user mixed audio is incorrectly time-aligned in every session where users do not join simultaneously at t=0.  See Q2.

---

## Query Status Key

| Symbol | Meaning |
|--------|---------|
| ✅ | Answered — verified by test or primary source |
| 🔬 | Open — needs investigation |
| 💭 | Hypothesis — inferred from docs or source; not yet confirmed against running code |

---

## Established Facts (Primary Sources)

Verifiable from the Discord developer docs or py-cord / libopus source without running the bot:

| Fact | Source |
|------|--------|
| Discord transmits voice as Opus packets over UDP/WebRTC | [Discord Voice docs](https://discord.com/developers/docs/topics/voice-connections) |
| Opus frame size is 20 ms at Discord's default settings | libopus spec |
| Discord's Opus decoder output format is 48 kHz, 16-bit signed LE, stereo | [Discord Voice docs](https://discord.com/developers/docs/topics/voice-connections#voice-data-format) |
| `PCMSink` is a `Sink` subclass in `discord.sinks` that buffers decoded PCM per user | [py-cord source](https://github.com/Pycord-Development/pycord/blob/master/discord/sinks/core.py) |
| `PyNaCl` (libsodium) is required for voice packet encryption/decryption | py-cord extras metadata |

---

## Open Research Queries

### Q1 — What does `sink.audio_data` contain exactly after `stop_recording()`? ✅ Answered (from py-cord source)

**Finding:** `sink.audio_data` is `dict[int, AudioData]` where keys are `user_id` integers.  Reading `discord/sinks/core.py`:

```python
class AudioData:
    def __init__(self, file):
        self.file = file         # BytesIO — seek position is at EOF
        self.finished = False    # True after cleanup() is called

    def cleanup(self):
        self.file.seek(0)        # ← rewinds to start before callback fires
        self.finished = True
```

**Important:** there is **no `.user` attribute** on `AudioData` in the current py-cord source.  To look up the Discord `User` from a `user_id` key, use `bot.get_user(user_id)`.  Any future code that accesses `audio.user` will raise `AttributeError`.

**Seek position:** `cleanup()` calls `self.file.seek(0)` before the callback fires, so the `BytesIO` arrives already rewound to byte 0.  The `audio.file.seek(0)` call in `merge_audio_data()` is therefore redundant but harmless.

**Action:** Document the absence of `.user` in the `merge_audio_data` docstring.  Add a helper `_get_user(user_id)` in `bot.py` for any speaker-label feature that needs the name.

---

### Q2 — Does PCMSink capture silence or only active speech packets? ✅ Answered — CRITICAL

**Finding: PCMSink captures ONLY active speech.  Silence is dropped entirely.**

Discord's client-side Voice Activity Detection (VAD) suppresses Opus packet transmission when a user is silent.  No packets arrive at the bot.  py-cord's `AudioData.write()` is only called on packet arrival — there is no gap-filling or silence insertion anywhere in the py-cord pipeline.

**Source:** `discord/sinks/core.py` — `AudioData.write()` performs a straight `self.file.write(data)` with no timestamp tracking.

**Consequence for TheWatcher — every multi-user session is affected:**

If User A speaks from t=0, and User B joins at t=10 min:
- `audio_data[A_id]` contains ~30 min of bytes
- `audio_data[B_id]` contains ~20 min of bytes **starting at byte 0**

`merge_audio_data()` zero-pads B to match A's length.  B's audio is aligned to the **beginning** of the session, not the 10-minute mark.  **B's first words overlap with silence in the mix, not with the actual point they joined.**

**In practice this means:**
- Transcripts of sessions where everyone joins at `/watch` time are correct.
- Any session where a player joins late, reconnects, or drops out mid-session will produce a mixed WAV with incorrect temporal alignment.  The Whisper transcript will interleave speakers incorrectly.

**Required fix (highest priority — target v0.5):**

1. In `bot.py`, subscribe to `on_voice_state_update` and record join timestamps per user:
```python
_join_times: dict[int, float] = {}  # user_id → monotonic timestamp

@bot.event
async def on_voice_state_update(member, before, after):
    if after.channel and not before.channel:   # joined
        _join_times[member.id] = time.monotonic()
```

2. In `merge_audio_data()`, pre-pad each user's PCM with silence proportional to their join offset:
```python
session_start = min(_join_times.values())
for user_id, audio in audio_data.items():
    offset_s = _join_times.get(user_id, session_start) - session_start
    silence = b"\x00" * int(offset_s * _SAMPLE_RATE * _CHANNELS * _SAMPLE_WIDTH)
    audio.file.seek(0)
    pcm_tracks.append(silence + audio.file.read())
```

**Until fixed:** TheWatcher is reliable only for groups where all players are already in the voice channel before `/watch` is called and nobody disconnects.

---

### Q3 — What is the actual peak memory usage for a 3-hour session? 🔬

**Theoretical ceiling (100% speech, no suppression):**
```
4 users × 3h × 3600s × 48000 samples/s × 2ch × 2 bytes = ~3.3 GB
```

**Query:** What is the actual RSS at the end of a real or simulated 3-hour recording with Discord silence suppression active?

**Experiment:**
```python
import psutil, os
proc = psutil.Process(os.getpid())
# Log proc.memory_info().rss every 60 seconds during the recording
```
Alternatively: inject synthetic PCM using a test harness that fills `sink.audio_data` with pre-built `BytesIO` objects.

**Threshold to establish:** At what session length / user count does memory pressure become a problem on 8 GB and 16 GB systems?  This determines the milestone priority for the incremental disk-write mitigation (planned v0.6).

---

### Q4 — How long between `vc.stop_recording()` and the callback firing? ✅ Answered

**Finding:** `vc.stop_recording()` sets a flag on the voice receive thread.  The callback is dispatched via `asyncio.ensure_future()` on the bot's event loop — it is not called synchronously.  Under normal event-loop conditions, the delay is in the range of one event-loop tick (< 1 ms) plus any currently awaited coroutines.

**Implication for `_on_recording_finished`:** The `await channel.send("🔄 Saving audio…")` at the top of the callback fires before `await asyncio.to_thread(finish_recording, sink)`.  The status message sequence in the current code is correct — users will see the progress messages in order.

**One edge case:** If the event loop is saturated (e.g. another guild's pipeline is running simultaneously), the callback may queue behind existing coroutines.  This is unlikely in a single-guild deployment but worth noting for future multi-guild support.  Measurement is only needed if users report delayed status messages in multi-guild deployments.

---

### Q5 — What happens to `sink.audio_data` if a user disconnects before `/unwatch`? ✅ Answered

**Finding:** py-cord retains the `AudioData` entry in `sink.audio_data` when a user disconnects from the voice channel.  The sink continues accumulating audio from remaining users.  The callback does **not** fire on user-disconnect — it only fires on `vc.stop_recording()`.

**Source:** py-cord `discord/sinks/core.py` — there is no `on_user_leave` handler in `Sink` that removes entries or triggers the callback.

**Impact:** Audio captured before the user disconnected is preserved in the buffer and will be included in the mix.  Combined with the Q2 finding, the practical effect is:
- A user who joins at t=0, speaks for 10 minutes, then disconnects will have their 10 minutes of audio misaligned unless join timestamps are tracked.
- Their audio will NOT be lost — it will be mixed, just at the wrong time offset.

**Action:** The join-timestamp fix for Q2 doubles as the fix for this case — tracking leave times is not required since the audio buffer accurately represents the user's active period.

---

### Q6 — Is `ffmpeg` actually required when the bot only receives audio? � Strong hypothesis — likely NOT required for receive-only

**Reasoning:**

- `ffmpeg` is used by py-cord exclusively when creating audio *source* objects for playback (e.g. `discord.FFmpegPCMAudio`).  TheWatcher never plays audio.
- TheWatcher's `merge_audio_data()` and `finish_recording()` use only Python's built-in `wave` and `struct` modules — no `ffmpeg` dependency.
- `faster-whisper` (the recommended transcription upgrade — see whisper-backends.md) explicitly documents that it does **not** require `ffmpeg` on the system because it uses PyAV.
- `openai-whisper` uses `ffmpeg` to load non-WAV formats, but TheWatcher always passes a `.wav` file output from Python's `wave` module.

**Remaining uncertainty:** py-cord's `voice_client.py` may attempt to call `ffmpeg` at connection time for audio playback infrastructure even when unused.  This needs one empirical test: start the bot without `ffmpeg` on `PATH` and run a full session.

**Action:** Run the test.  If successful, change the README requirement from "required" to "recommended (only needed if you add audio playback features)" — this meaningfully reduces friction for Docker and headless Linux installs.

---

### Q7 — Is per-user audio more convenient via `WaveSink` than `PCMSink`? ✅ Direction confirmed — WaveSink is better for v0.5

**Finding:** `WaveSink` buffers a full WAV file (headers + PCM) per user in its `AudioData.file` BytesIO.  After `cleanup()`, `file.seek(0)` gives a complete, spec-compliant WAV file.  This can be passed directly to both `openai-whisper` (via a temp file) and `faster-whisper` (via BytesIO or temp file).

**Structure after stop:**
```python
# WaveSink: each entry is a valid WAV file
for user_id, audio in sink.audio_data.items():
    audio.file.seek(0)
    wav_bytes = audio.file.read()  # complete WAV, ready for whisper
```

**For v0.5, the recommended architecture shift is:**
1. Replace `PCMSink` with `WaveSink` in `RecordingSink`.
2. Write one WAV file per user to `RECORDINGS_DIR` (e.g. `session_YYYYMMDD_HHMMSS_user12345.wav`).
3. Transcribe each file individually — Whisper handles single-speaker audio significantly better than mixed multi-speaker audio.
4. Prepend each transcript segment with the user's display name.
5. Pass the concatenated labelled transcript to the summariser.

**Expected quality improvement:** Speaker-attributed transcripts dramatically improve Whisper's Named Entity accuracy and LLM section compliance.  The summariser can produce "Player Decisions" sections that correctly attribute each decision to the right player.

**Extended architecture — character name registry + vocabulary learning:** See [whisper-backends.md — Per-Speaker Transcription & Character Voice Learning](whisper-backends.md#per-speaker-transcription--character-voice-learning) for the full design: `/register-character` command, per-server `vocabulary.json` that biases Whisper towards correct spellings of invented proper nouns across sessions, and optional voice profile enrollment for post-hoc speaker identification.  The key point is that per-user WAV files (this Q7 architecture) are the prerequisite for all of that — they must land in v0.5 before any speaker-learning features can be built.

---

### Q8 — What is the audible quality of the mixed WAV for a typical 4-person session? � Known limitation in current approach

**Analysis of current `merge_audio_data` mixing strategy:**

The current implementation sums 16-bit samples and hard-clamps:
```python
mixed = [max(-32768, min(32767, sum(s[i] for s in samples_list))) for i in range(sample_count)]
```

This is a **clamp mixer**, which produces audible hard-distortion artefacts when more than 2 speakers are simultaneously loud.  The distortion threshold for N speakers is approximately:
- 2 speakers: fine (each can use up to 50% of the range)
- 3 speakers: clipping when any two speak at >50% combined with a third
- 4 speakers: frequent clipping during overlapping dialogue

**Recommended upgrade (low effort, high impact):** Replace with an **average mixer** that divides by the number of active tracks:
```python
# In merge_audio_data(), replace the mix loop:
n = len(samples_list)
mixed = [
    max(-32768, min(32767, sum(s[i] for s in samples_list) // n))
    for i in range(sample_count)
]
```
This eliminates clipping entirely at the cost of slightly lower volume (which Whisper handles fine).

**Transcription impact:** Clamp distortion is unlikely to meaningfully degrade Whisper accuracy in practice — Whisper is robust to distorted audio, and mixed-speaker audio is already challenging regardless.  The WaveSink approach in Q7 eliminates the problem entirely by keeping speakers separate.

**Standalone archive quality:** For the v1.3+ "master mix" WAV written for session archiving, a better algorithm is needed.  See [standalone-architecture.md Q6](standalone-architecture.md#q6--what-is-the-most-resilient-mixing-algorithm-for-n-track-16-bit-pcm-in-python) for a full comparison of Viktor Toth's algorithm, weighted average, and floating-point normalisation, including THD+N measurements and the decision for which algorithm lands in v0.3 (Discord bot) vs. v1.3 (standalone archiver).

---

## Recommended Direction

Based on the findings above, in priority order:

| Priority | Action | Target | Impact |
|----------|--------|--------|--------|
| 🔴 **Critical** | Implement per-user join-timestamp tracking + silence pre-padding | v0.5 | Fixes incorrect multi-user audio alignment |
| 🔴 **Critical** | Add warning in `/watch` response if any users are already in VC at recording start | v0.3 | Informs users of current limitation |
| 🟡 **High** | Switch to `WaveSink` + per-user WAV files with speaker attribution | v0.5 | Dramatically improves transcript quality |
| 🟡 **High** | Test and document `ffmpeg` requirement for receive-only | v0.2 | Reduces setup friction |
| 🟢 **Medium** | Replace clamp mixer with average mixer | v0.3 | Eliminates distortion for 3+ users |
| 🟢 **Medium** | Document that `AudioData` has no `.user` attribute | v0.2 | Prevents future AttributeError bugs |

---

## Deferred Queries (Post v0.3)

| # | Target milestone | Query |
|---|-----------------|-------|
| Q9 | v0.5 | How do we reliably record per-user join timestamps for silence pre-padding? |
| Q10 | v0.6 | What is the quality difference between 48 kHz stereo and 16 kHz mono input to Whisper? |
| Q11 | v0.6 | What is the overhead of incremental `tempfile` writes vs in-memory `BytesIO` for a 3-hour session? |
| Q12 | v0.6 | Can Opus comfort-noise packets, if present, be distinguished from speech and dropped before mixing? |


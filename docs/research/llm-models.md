# Research: LLM Models for TTRPG Summarisation

**Status:** 🔬 Active — evaluations are planned; critical context window blocker identified for default model  
**Informs:** [ADR-0004](../adr/0004-ollama-for-llm.md), `src/summarizer.py`

> ❗ **Critical finding:** The current default `OLLAMA_MODEL=mistral` has an 8 192-token context window.  A typical 3-hour TTRPG session transcript is ~28 000–35 000 tokens.  Mistral will silently truncate roughly **75% of every real session** before it produces a summary.  The default must change to `llama3.1` (128k context) immediately.  See Q8.

---

## Query Status Key

| Symbol | Meaning |
|--------|---------|
| ✅ | Answered — measured on real or realistic synthetic data |
| 🔬 | Open — experiment designed but not yet run |
| 💭 | Hypothesis — inferred from published benchmarks or community reports; not measured by us |

---

## Evaluation Criteria

These criteria, and why they matter for TTRPG use specifically, define what we are measuring:

| Criterion | Why it matters for TTRPG |
|-----------|--------------------------|
| **Section compliance** | The model must produce all five required Markdown sections on every run, not sometimes |
| **Named entity fidelity** | "Theron Ashveil" must not become "Theron" or "the character" — invented proper nouns are the hardest part of TTRPG transcripts |
| **Hallucination rate** | Invented events or NPCs in a session log cause real confusion at the table next session |
| **Context window** | A 3-hour session transcript at ~150 words/min ≈ 27 000 words ≈ 35 000 tokens; must not be silently truncated |
| **Wall-clock latency** | The Discord user is waiting; beyond ~3 minutes the response feels broken |
| **RAM headroom** | Ollama + the bot process must fit alongside the OS on the user's machine |

---

## Test Harness Design 🔬

Before running any model, build a reproducible test harness:

**Input:** A fixed 8 000-token synthetic TTRPG session transcript that includes:
- At least 6 invented proper nouns (character names, place names, spell names)
- One event that did NOT happen (to measure hallucination rate)
- A section with overlapping NPC dialogue
- A late-session cliffhanger

**Ground truth:** A hand-authored "gold standard" summary covering all five sections.  Keep it under version control at `tests/fixtures/gold_summary.md`.

**Metrics to record per run:**

| Metric | How to measure |
|--------|---------------|
| Section present | Parse output for each of the five `##` headings |
| Named entity accuracy | Count matches of the 6 known proper nouns (exact and case-insensitive) |
| Hallucination presence | Check whether the planted false event appears in the output |
| Tokens/second | `time.monotonic()` around the `client.chat()` call ÷ `response.eval_count` |
| RSS peak | `psutil.Process().memory_info().rss` before and after the call |

**Run each model 5 times** to surface non-determinism.  Use `temperature=0` for reproducibility.

---

## Model Query Matrix

Models to evaluate, in priority order.  **None of these have been run yet.**

### Q1 — `mistral:7b-instruct-q4_K_M` (proposed default) 🔬

**Install:** `ollama pull mistral`
**Context window:** 8 192 tokens
**Expected RAM (from Ollama model card):** ~4.1 GB
**Community reports:** Widely cited as good at structured instruction-following for summarisation tasks.

**Open questions:**
- Does it consistently produce all five sections without prompt tweaks?
- Does it hallucinate proper noun variants (e.g. "Ashe" for "Ashveil")?
- What happens when the transcript exceeds 8k tokens — silent truncation or error?

---

### Q2 — `llama3:8b-instruct-q4_K_M` 🔬

**Install:** `ollama pull llama3`
**Context window:** 8 192 tokens
**Expected RAM:** ~4.7 GB

**Open questions:**
- Does llama3's stronger instruction-following reputation hold for structured domain-specific output?
- Is named entity preservation meaningfully better than Mistral?
- Does it add narrative "flavour text" not present in the transcript?

---

### Q3 — `gemma2:9b-instruct-q4_K_M` 🔬

**Install:** `ollama pull gemma2`
**Context window:** 8 192 tokens
**Expected RAM:** ~5.5 GB

**Open questions:**
- Community reports suggest gemma2 sometimes merges adjacent sections — does this occur with our prompt?
- Is the speed penalty vs Mistral/Llama3 significant enough to matter for UX (>3 min for a 3h transcript)?

---

### Q4 — `mixtral:8x7b-instruct-q4_K_M` 🔬

**Install:** `ollama pull mixtral`
**Context window:** 32 768 tokens
**Expected RAM:** ~26 GB — only testable on 32 GB+ systems

**Open questions:**
- Does the 32k context window meaningfully improve summaries of very long (4h+) sessions?
- At ~8 tok/s CPU throughput (hypothesis from published llama.cpp benchmarks), is a 3-hour transcript summary deliverable in under 10 minutes?
- Can GPU offloading with 8 GB VRAM bring this to acceptable speed on consumer hardware?

---

### Q5 — `phi3:3.8b-mini-instruct-q4_K_M` (minimum-hardware target) 🔬

**Install:** `ollama pull phi3`
**Context window:** 4 096 tokens — will truncate most real sessions
**Expected RAM:** ~2.4 GB

**Open questions:**
- What is the quality floor on a system with only 4–6 GB RAM available for Ollama?
- At what transcript length does the 4k context limit visibly degrade the summary?
- Is truncation silent or does the model indicate missing content?

---

### Q6 — `llama3.1:8b-instruct-q4_K_M` (long-context candidate) 🔬

**Install:** `ollama pull llama3.1`
**Context window:** 131 072 tokens
**Expected RAM:** ~4.9 GB

**Primary query:** Does the 128k context window eliminate the transcript-chunking problem for very long sessions, at RAM cost comparable to llama3?

---

### Q7 — `qwen2.5:7b-instruct-q4_K_M` (multilingual candidate) 🔬

**Install:** `ollama pull qwen2.5`
**Context window:** 128k tokens

**Primary query:** For TTRPG groups playing in French, German, or Spanish — does qwen2.5 preserve proper nouns and produce correctly structured output in the session's language without adding a language directive to the system prompt?

---

## Prompt Engineering Queries 🔬

The system prompt in `src/summarizer._SYSTEM_PROMPT` has not been systematically optimised.  These queries should be run **after** the baseline model evaluations:

| Query | Experiment |
|-------|------------|
| **P1** Does "You MUST include all five sections" improve section compliance for weaker models? | A/B test on phi3 and gemma2 |
| **P2** Does explicitly listing proper nouns in the user message improve fidelity? | Prepend known character names to the transcript; measure entity accuracy delta |
| **P3** Does `temperature=0` vs `temperature=0.3` affect hallucination rate meaningfully? | 10 runs at each temperature; count false-event occurrences |
| **P4** What is the minimum viable transcript length before summaries become too generic? | Test with 500 / 1000 / 2000 / 5000 token inputs; evaluate specificity |
| **P5** Does asking for JSON output instead of freeform Markdown improve section compliance? | Compare structured JSON → rendered Markdown vs direct Markdown |

---

## Context Window & Truncation — Critical Analysis ✅ Answered by Arithmetic

**Q8 — The current default will truncate most real sessions.**

Token budget calculation for a typical TTRPG session:

| Session length | Words (@ 120 wpm avg) | Tokens (@ 1.3 tok/word) | Fits in 8k? | Fits in 128k? |
|---|---|---|---|---|
| 1 hour | 7 200 | ~9 400 | ❌ No | ✅ Yes |
| 2 hours | 14 400 | ~18 700 | ❌ No | ✅ Yes |
| 3 hours | 21 600 | ~28 100 | ❌ No | ✅ Yes |
| 4 hours | 28 800 | ~37 400 | ❌ No | ✅ Yes |

**Even a 1-hour session exceeds Mistral’s 8 192-token context window.**

**What Ollama does on overflow:** Ollama uses `num_ctx` (the model’s context size) as a hard limit.  When the input exceeds it, Ollama silently truncates from the **beginning** of the context window.  The model receives only the most recent N tokens — meaning it will summarise the end of the session and have no knowledge of the first hour or more.  There is no error message.
> ⚠️ **Additional Ollama behaviour:** Ollama *also* defaults the runtime `num_ctx` to **2 048 tokens** regardless of the model's architectural maximum — even `llama3.1` (128k architectural limit) will truncate at 2 048 tokens unless `num_ctx` is explicitly set in every API call.  For the Discord bot, the fix is to pass `options={"num_ctx": <calculated_value>}` to `client.chat()`.  For the standalone application, an adaptive context manager that queries the model's architectural limit and sets `num_ctx` accordingly is required — see [standalone-architecture.md Q8](standalone-architecture.md#q8--how-to-manage-num_ctx-dynamically-in-a-standalone-app-to-prevent-model-amnesia).
**Fix — change the default model in `src/summarizer.py`:**
```python
# Before:
model = os.getenv("OLLAMA_MODEL", "mistral")      # 8k context

# After:
model = os.getenv("OLLAMA_MODEL", "llama3.1")     # 128k context
```

Also update `.env.example` and `docs/configuration.md`.

**Why `llama3.1:8b` specifically:**
- 128k context window handles even 6-hour sessions comfortably
- 8B parameters, Q4_K_M quantisation ≈ 4.9 GB RAM — fits on 8 GB machines
- Instruction-following capability is comparable to or better than Mistral 7B
- `ollama pull llama3.1` (auto-selects the 8B Q4 variant)

**For users on 4–6 GB RAM:** Document `phi3` as the low-resource option with a clear warning that sessions over 1 hour will be truncated.

**Alternative: chunked summarization (v0.5+)**
If [chunked transcription](../research/whisper-backends.md#chunked-recording--transcription-architecture) is implemented, per-chunk summaries (~5 minutes each → ~600 tokens per chunk) can be merged at session end via a second LLM pass.  This would allow 8k models to work on any session length.  However it introduces the risk of cross-chunk event loss (events spanning the chunk boundary may be attributed to the wrong chunk or dropped).  For v0.3, the simpler path is: chunked transcription + full-transcript summarization with `llama3.1` (128k context).

---

## System Prompt Analysis and Improvements 💭

The current `_SYSTEM_PROMPT` in `src/summarizer.py` is well-structured but has two gaps that empirical testing is likely to confirm:

**Gap 1: No explicit anti-hallucination instruction**

The current prompt says *"Preserve character names, place names, and important story details exactly as mentioned in the transcript"* but does not explicitly forbid inventing content.  Models — especially smaller ones — will often fill gaps in the transcript with plausible-sounding fiction.

**Recommended addition** at the end of the system prompt:
```
IMPORTANT: Only include events, characters, and details that appear in the transcript.
Do not invent, infer, or embellish. If a section has no relevant content, write
"Nothing notable this session" rather than fabricating content.
```

**Gap 2: No fallback for empty sections**

When the session has no NPC interactions (e.g. a pure exploration session), some models will either omit the `## NPC Interactions` section (breaking section compliance) or invent interactions.

**Recommended addition** after the section list:
```
If a section does not apply to this session, include the heading and write
"None this session" beneath it. Never omit a section.
```

**Gap 3: Language instruction for non-English groups**

Add to the end:
```
Respond in the same language as the transcript.
```

These three additions are low-risk (they constrain the model) and high-value (they improve consistency).  They should be added to `_SYSTEM_PROMPT` before any model evaluation is run so all models are tested against the same improved baseline.

---

## Recommended Direction

| Priority | Action | Target | Impact |
|----------|--------|--------|--------|
| 🔴 **Critical** | Change `OLLAMA_MODEL` default from `mistral` → `llama3.1` | v0.2 | Eliminates 75%+ transcript truncation on every real session |
| 🔴 **Critical** | Add anti-hallucination + empty-section instructions to `_SYSTEM_PROMPT` | v0.2 | Reduces invented events; improves section compliance |
| 🟡 **High** | Add language passthrough instruction to `_SYSTEM_PROMPT` | v0.2 | Enables non-English groups without config changes |
| 🟡 **High** | Add a `/model` command or `OLLAMA_MODEL` note in `/watch` response | v0.3 | Users should know which model is running |
| 🟡 **High** | Build and run the test harness (Q1–Q7 evaluations) | v0.3 | Confirms model choice and prompt quality with real data |
| 🟢 **Medium** | Add context window check: warn if transcript token estimate exceeds 75% of model’s context | v0.3 | Proactive warning before truncation occurs |
| 🟣 **Low** | Evaluate `qwen2.5:7b` for multilingual groups | v0.4 | Strong multilingual support, 128k context |

**Minimum viable model recommendation by hardware:**

| Available RAM (for Ollama) | Recommended model | Context window | Notes |
|---------------------------|------------------|----------------|-------|
| ≥ 8 GB | `llama3.1:8b` | 128k | New default — handles all real sessions |
| 6–8 GB | `mistral:7b` | 8k | Warn users sessions > 45 min will be truncated |
| 4–6 GB | `phi3:3.8b` | 4k | Sessions > 20 min truncated; quality noticeably reduced |
| ≥ 16 GB | `llama3.1:8b` or `qwen2.5:14b` | 128k | Larger model for better entity fidelity if RAM allows |

---

## Deferred Evaluation Candidates

| Model | Why deferred | Evaluate when |
|-------|-------------|---------------|
| `deepseek-r1:7b` | Reasoning-focused; chain-of-thought overhead may not benefit structured summarisation | After P5 (structured output) results |
| `gemma3:12b` | Released after v0.1 planning; community reports promising | v0.3 evaluation cycle |
| Any fine-tuned TTRPG model | None widely available yet; monitor Hugging Face | Ongoing |


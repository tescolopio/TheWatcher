# User Stories — v1.0 Discord Bot Track

Stories covering the v0.1 MVP through the stable v1.0 release.
See [index.md](index.md) for personas and the ID system.

---

## Recording & Core Pipeline

### US-001 — Start recording a session  ✅ Implemented

**As a** GM (Sam),
**I want to** type `/watch` in a Discord channel to make the bot join my voice channel and begin recording,
**so that** the session is captured without me having to set up any external software.

**Acceptance criteria:**
- [ ] Bot joins the voice channel the invoking user is currently in
- [ ] Bot sends a confirmation message: "🎙️ Recording started in **#channel-name**"
- [ ] If the invoking user is not in a voice channel, bot replies with a clear error and does not crash
- [ ] If a recording is already active in this guild, bot replies with an error indicating which channel is being recorded
- [ ] Recording begins capturing all participants present at the time of `/watch` and any who join afterward

**Milestone:** v0.1
**Notes:** Current implementation uses `PCMSink`; per-user WAV separation is planned for v0.5 (US-017).

---

### US-002 — Stop recording and receive session notes  ✅ Implemented

**As a** GM (Sam),
**I want to** type `/unwatch` to stop recording and automatically receive a structured session summary,
**so that** the notes are ready without any manual post-processing.

**Acceptance criteria:**
- [ ] Bot leaves the voice channel
- [ ] Bot sends a "processing" status message immediately (not after processing completes)
- [ ] Full pipeline runs: WAV save → transcription → LLM summarisation → Obsidian note write
- [ ] On success, bot posts a confirmation message with the note filename and vault path
- [ ] On success, the Markdown note exists on disk with correct YAML front-matter and all five required sections
- [ ] If `/unwatch` is called when no recording is active, bot replies with a clear error

**Milestone:** v0.1
**Notes:** Status message sequencing confirmed correct in bot.py `_on_recording_finished`; see discord-voice.md Q4.

---

### US-003 — Player joins the session late

**As a** player (Alex),
**I want to** join the voice channel after the session has already started and have my audio captured from that point forward,
**so that** arriving a few minutes late does not prevent me from appearing in the session notes.

**Acceptance criteria:**
- [ ] Audio from a late-joining user is captured from the moment they join
- [ ] Their audio is correctly time-aligned in the merged WAV (not shifted to t=0)
- [ ] The session note does not incorrectly attribute their early silence to speech
- [ ] No error or crash occurs when a new user joins mid-recording

**Milestone:** v0.3
**Notes:** Current `PCMSink` drops silence — a user joining at t=10min has their WAV bytes starting at position 0, causing mis-alignment.  Fix: join-timestamp pre-padding.  See discord-voice.md Q2 (CRITICAL finding).

---

### US-004 — Player disconnects and reconnects mid-session

**As a** player (Alex),
**I want to** disconnect from voice and reconnect (e.g. due to a network drop) without the recording being corrupted or the bot crashing,
**so that** a brief connection issue does not ruin the session notes.

**Acceptance criteria:**
- [ ] Bot continues recording other participants when one disconnects
- [ ] When the disconnected user reconnects, their audio resumes being captured
- [ ] Audio from both their original and reconnected segments is included in the final output
- [ ] No error is logged at WARN level or above solely due to the disconnect/reconnect

**Milestone:** v0.3
**Notes:** Confirmed in discord-voice.md Q5 that audio is retained on disconnect.  The pre-padding fix for US-003 must also handle the reconnect case (second join timestamp).

---

## Setup & Configuration

### US-005 — First-time installation

**As a** GM (Sam),
**I want to** install RPG Watcher on my home server by following a single README section,
**so that** I can have the bot running in a real voice session within 30 minutes of first discovering the project.

**Acceptance criteria:**
- [ ] `README.md` contains a "Quick Start" section covering: Python version, `pip install`, `.env` setup, Ollama pull, bot token, invite URL generation
- [ ] `.env.example` contains every supported environment variable with a description and example value
- [ ] Following the Quick Start on a clean machine (Python 3.11+, no prior deps) produces a running bot in under 30 minutes
- [ ] The first `/watch` → `/unwatch` cycle produces a Markdown note without further intervention

**Milestone:** v0.2
**Notes:** Ties to US-028 (full setup guide in v0.9 docs).

---

### US-006 — Configure the Obsidian vault path

**As a** GM (Sam),
**I want to** tell the bot where my Obsidian vault is located so notes are written there automatically,
**so that** I never have to manually move or copy files after a session.

**Acceptance criteria:**
- [ ] `OBSIDIAN_VAULT_PATH` env var is documented in `.env.example` with a clear example
- [ ] `OBSIDIAN_NOTES_FOLDER` env var sets a sub-folder within the vault (default: `Session Notes`)
- [ ] If the vault path does not exist, bot logs a clear error at startup and refuses to start rather than silently failing later
- [ ] Notes are written to `<OBSIDIAN_VAULT_PATH>/<OBSIDIAN_NOTES_FOLDER>/YYYY-MM-DD — Session Title.md`

**Milestone:** v0.2

---

### US-007 — Check bot status and active configuration

**As a** GM (Sam),
**I want to** type `/status` to see what the bot is currently configured to use,
**so that** I can confirm the right Whisper backend and Ollama model are active before starting an important session.

**Acceptance criteria:**
- [ ] `/status` replies with an embed showing: bot latency, Ollama connectivity (✅/❌ + model name), active Whisper backend, current `WHISPER_MODEL`, vault path, available disk space (MB and % used on the relevant drive)
- [ ] If Ollama is unreachable, the embed shows ❌ with a hint (e.g. "Is Ollama running? `ollama serve`")
- [ ] Response is ephemeral (only Sam sees it)
- [ ] Command completes in under 3 seconds

**Milestone:** v0.3

---

### US-008 — Bot restarts without losing an in-progress recording

**As a** GM (Sam),
**I want to** be warned if the bot process restarts or crashes while recording is active,
**so that** I know to check for a partial audio file rather than assuming the session is lost.

**Acceptance criteria:**
- [ ] Active recording state (guild ID, channel ID, start time) is persisted to SQLite before any audio is written
- [ ] On bot startup, if a `recording` state entry exists in the database, a warning is posted to a configurable alert channel (or logged prominently)
- [ ] The partial WAV file is never deleted automatically after a crash; it remains in `RECORDINGS_DIR`
- [ ] `/sessions` command lists the interrupted session with status `interrupted` and the path to the partial WAV

**Milestone:** v0.3

---

## Error Recovery

### US-009 — Ollama is unreachable when the session ends

**As a** GM (Sam),
**I want to** receive the raw transcript as a fallback note even when the LLM summariser fails,
**so that** no session data is ever silently discarded because of a service dependency being down.

**Acceptance criteria:**
- [ ] If the Ollama call fails (connection refused, timeout, or HTTP error), a fallback note is written to the vault tagged `#needs-summary` with the raw transcript as the note body
- [ ] Bot posts a Discord message explaining what happened and where the fallback note is
- [ ] After `OLLAMA_MAX_RETRIES` attempts with exponential back-off, the fallback path is taken (not an infinite loop)
- [ ] The WAV file is retained until the user explicitly cleans it up
- [ ] Once Ollama comes back online, Sam can re-run summarisation against the fallback note's transcript (a future `/retry-summary` command; the fallback note is designed to make this easy)

**Milestone:** v0.3

---

### US-010 — Disk nearly full when recording starts

**As a** GM (Sam),
**I want to** be warned before a session starts if there is not enough disk space to store the recording,
**so that** I am not 3 hours into a session only to have the bot fail silently or crash.

**Acceptance criteria:**
- [ ] On `/watch`, bot checks available disk space on the `RECORDINGS_DIR` volume
- [ ] If available space is below `MIN_FREE_DISK_MB` (default 500 MB), `/watch` is refused with a clear message: "⚠️ Only 312 MB free. I need at least 500 MB to record safely. Free up space or lower `MIN_FREE_DISK_MB`."
- [ ] Estimate of required space shown in the warning (e.g. "A 3-hour session uses approx 1.0 GB")
- [ ] If the check cannot be performed (permission error), `watch` proceeds but a warning is logged

**Milestone:** v0.3

---

### US-011 — Pipeline fails mid-processing after recording ends

**As a** GM (Sam),
**I want to** always have the WAV file available after a session ends even if transcription or summarisation fails,
**so that** I can re-run the pipeline manually once the issue is fixed without re-recording.

**Acceptance criteria:**
- [ ] WAV file is written to `RECORDINGS_DIR` as the very first step of `_on_recording_finished`, before transcription begins
- [ ] If transcription fails, bot posts a Discord message with the WAV path and the error
- [ ] If summarisation fails, bot posts a message with the transcript text (or path to a saved transcript file) and the error
- [ ] WAV file is never automatically deleted unless all pipeline stages have completed successfully
- [ ] A `KEEP_WAV=true` env var (default: `false`) forces WAV files to be retained even after successful pipeline runs

**Milestone:** v0.3

---

## User Experience & Discord Output

### US-012 — See live pipeline progress in Discord

**As a** player (Alex),
**I want to** see the bot update a single message in real time as it processes the session,
**so that** I know what stage the pipeline is at and roughly how long it will take.

**Acceptance criteria:**
- [ ] A single Discord message is posted when `/unwatch` is called and then edited (not replaced) as each stage completes
- [ ] Stage labels: 💾 Saving audio… → 🔤 Transcribing… → 🧠 Summarising… → 📝 Writing note… → ✅ Done
- [ ] Each completed stage shows a checkmark and the time it took (e.g. "🔤 Transcribed in 1m 42s")
- [ ] If a stage fails, the message updates with ❌ and a brief error description
- [ ] A Discord "typing" indicator is shown while each stage runs

**Milestone:** v0.4

---

### US-013 — Open the session note directly from Discord

**As a** GM (Sam),
**I want to** click a button in the completion Discord message to open the note in Obsidian immediately,
**so that** I can review or annotate the notes while the session is still fresh.

**Acceptance criteria:**
- [ ] Completion embed includes an "Open in Obsidian" button using an `obsidian://open?vault=…&file=…` deep link URI
- [ ] The URI is URL-encoded correctly (spaces, special characters in vault/file names handled)
- [ ] Button is shown only when `OBSIDIAN_VAULT_PATH` is configured
- [ ] Clicking the button on a machine that does not have Obsidian installed fails gracefully (handled at the OS level; no bot action required)

**Milestone:** v0.4

---

### US-014 — Set an active campaign for note organisation

**As a** GM (Sam),
**I want to** tell the bot which campaign is currently running so that all subsequent session notes are organised under that campaign,
**so that** my vault stays clean across multiple concurrent campaigns.

**Acceptance criteria:**
- [ ] `/campaign set <name>` stores the campaign name per-guild in the database
- [ ] While a campaign is active, notes are written to `<OBSIDIAN_NOTES_FOLDER>/<campaign-name>/YYYY-MM-DD — Session Title.md`
- [ ] Note YAML front-matter includes `campaign: <name>`
- [ ] `/campaign clear` removes the active campaign; notes revert to the flat folder
- [ ] `/campaign` (no subcommand) shows the currently active campaign or "No campaign active"
- [ ] Campaign name is shown in the pipeline progress embed

**Milestone:** v0.4

---

### US-015 — Change the LLM model without editing the `.env` file

**As a** GM (Sam),
**I want to** switch the active Ollama model from a Discord command,
**so that** I can try a different model for one session without restarting the bot or editing config files.

**Acceptance criteria:**
- [ ] `/config set model <model-name>` updates the active model for this guild, stored in the database
- [ ] Per-guild config overrides the global `.env` value for that guild only
- [ ] `/config show` lists all current per-guild settings vs global defaults
- [ ] If the model name is not available in Ollama, bot warns "⚠️ Model 'xyz' not found in Ollama. Available: mistral, llama3.1…" (pulls from `ollama list`)
- [ ] `/config` is restricted to users with the "Manage Server" permission

**Milestone:** v0.4

---

### US-016 — Summary too long for a single Discord message

**As a** player (Alex),
**I want to** read the full session summary in Discord even for a long 4-hour session,
**so that** I don't have to open Obsidian just to see what happened.

**Acceptance criteria:**
- [ ] If summary text exceeds 4 096 characters (Discord embed limit), it is split across multiple embeds (paginated)
- [ ] Each page is labelled "Summary (1/3)", "Summary (2/3)", etc.
- [ ] Section headings are never split across pages — a page break occurs before a heading, not mid-section
- [ ] The final embed always includes the "Open in Obsidian" button (US-013)

**Milestone:** v0.4

---

## Speaker Identification & Character Mapping

### US-017 — Register a character name

**As a** player (Alex),
**I want to** register my character's name with the bot once,
**so that** every future session note attributes my dialogue to my character rather than my Discord username.

**Acceptance criteria:**
- [ ] `/register-character character:<name>` stores the mapping `user_id → character name` per guild in the database
- [ ] Optional `player:<ooc-name>` parameter stores the out-of-character player name
- [ ] `/characters` lists all registered characters for this guild
- [ ] `/register-character character:<new-name>` updates an existing registration (no duplicate entries)
- [ ] Character name is included in the "cast list" injected into the LLM system prompt at summarisation time
- [ ] A `/unregister-character` command removes the registration

**Milestone:** v0.5

---

### US-018 — Transcript lines are attributed to the correct speaker

**As a** GM (Sam),
**I want to** see each line of the raw transcript labelled with the speaker's character name,
**so that** the LLM summariser can correctly attribute decisions, actions, and dialogue.

**Acceptance criteria:**
- [ ] Each user's audio is transcribed separately (per-user WAV via WaveSink); results are sorted by utterance start timestamp
- [ ] Each transcript line is prefixed: `[Theron Ashveil]: "I draw my sword."`
- [ ] If a user has no registered character, their Discord display name is used as the fallback label
- [ ] The full labelled transcript is included in the Obsidian note under a `## Raw Transcript` section
- [ ] The `initial_prompt` passed to the Whisper backend includes the character's name and the session vocabulary (US-019)

**Milestone:** v0.5

---

### US-019 — Invented proper nouns are spelled consistently across sessions

**As a** GM (Sam),
**I want to** add world-specific vocabulary (character names, place names, item names) once, so that Whisper stops misspelling them every session,
**so that** the notes are clean and consistent without manual editing after every session.

**Acceptance criteria:**
- [ ] After each session, named entities are extracted from the LLM summary and added to a per-guild `vocabulary.json` with a frequency counter
- [ ] Before transcription, the top-20 most frequent terms are built into an `initial_prompt` string: "Known names and terms: Theron Ashveil, Mirethaal, the Sundering Blade."
- [ ] `/vocab add <word>` manually adds a term to the guild vocabulary
- [ ] `/vocab list` displays the current vocabulary with frequency counts
- [ ] `/vocab remove <word>` removes an incorrect entry
- [ ] After 3 sessions, a term that was originally transcribed inconsistently converges to the canonical spelling

**Milestone:** v0.5

---

### US-020 — Character changes between sessions

**As a** player (Alex),
**I want to** update my registered character when my character dies, retires, or I start a new campaign,
**so that** the notes for the new campaign use my new character's name, not the old one.

**Acceptance criteria:**
- [ ] `/register-character` with a new name overwrites the previous registration for that user in that guild
- [ ] Old sessions' notes are not retroactively changed (they were written with the old name at the time)
- [ ] If the campaign is changed (US-014), the character registry is campaign-scoped: registrations carry over by default but can be set per-campaign with `/register-character campaign:<name> character:<name>`

**Milestone:** v0.5

---

## Audio Quality

### US-021 — Mic check before the session starts

**As a** GM (Sam),
**I want to** record a quick 5-second clip and hear it back in Discord,
**so that** I can confirm everyone's mic is working and the bot is capturing audio correctly before committing to a 4-hour session.

**Acceptance criteria:**
- [ ] `/preview` joins the voice channel, records for 5 seconds, leaves, and sends an audio file (`.ogg` or `.mp3`) as a Discord attachment
- [ ] The preview clip includes all users currently in the voice channel (mixed)
- [ ] Command completes and posts the clip within 15 seconds of invocation
- [ ] If the bot is already recording (via `/watch`), `/preview` is rejected with an error

**Milestone:** v0.6

---

### US-022 — Loud user doesn't drown out others

**As a** player (Alex),
**I want to** be heard clearly even when another player speaks loudly or has a hot mic,
**so that** my contributions are captured in the transcript rather than clipped out by distortion.

**Acceptance criteria:**
- [ ] Each per-user audio track is RMS-normalised to a target level before mixing (with WaveSink, v0.5)
- [ ] The normalisation target is configurable (`NORMALISE_TARGET_DBFS`, default −18 dBFS)
- [ ] A per-user track that is entirely silence is not normalised (avoids amplifying noise floor)
- [ ] The mixed WAV has no hard-clipping artefacts for typical 4-person sessions

**Milestone:** v0.6

---

## Multi-Server & Access Control

### US-023 — Two Discord servers record simultaneously

**As a** server admin (Jordan),
**I want to** run a single RPG Watcher instance that serves multiple Discord servers simultaneously without the sessions interfering with each other,
**so that** I don't need to run a separate bot process per guild.

**Acceptance criteria:**
- [ ] All active recording state is keyed by `guild_id`; state from Guild A is never visible to Guild B
- [ ] Two guilds can be in the `recording` state at the same time without errors
- [ ] Per-guild configuration (model, campaign, character registry, vocabulary) is completely isolated
- [ ] A pipeline failure in one guild does not affect an active recording in another

**Milestone:** v0.7

---

### US-024 — Restrict recording to specific roles

**As a** server admin (Jordan),
**I want to** configure which roles are allowed to start and stop recordings,
**so that** random server members cannot trigger a recording or expose voice channel audio.

**Acceptance criteria:**
- [ ] `ALLOWED_ROLE_IDS` env var (comma-separated Discord role IDs) restricts `/watch` and `/unwatch`
- [ ] If set, users without one of the allowed roles receive an ephemeral "You don't have permission to do this" reply
- [ ] If not set, any server member can use the commands (existing behaviour)
- [ ] Bot startup logs the effective access control policy ("Restricted to roles: 123, 456" or "Open to all members")
- [ ] `/config` (for changing model, campaign, etc.) is always restricted to "Manage Server" permission regardless of `ALLOWED_ROLE_IDS`

**Milestone:** v0.7

---

### US-025 — Bot refuses a second simultaneous recording in the same guild

**As a** GM (Sam),
**I want to** be clearly told if a recording is already in progress when I try to start another one,
**so that** accidental double-recording attempts don't silently produce corrupt output.

**Acceptance criteria:**
- [ ] If `/watch` is invoked while a recording is already active in the same guild, the bot replies with: "⚠️ Already recording in **#channel-name** (started at 7:34 PM). Use `/unwatch` to stop it first."
- [ ] The guard is enforced even if the previous `/watch` was issued by a different user
- [ ] The check is race-condition safe (no two concurrent `/watch` calls can both succeed)

**Milestone:** v0.7

---

## Distribution

### US-026 — Install via Docker

**As a** server admin (Jordan),
**I want to** run RPG Watcher in a Docker container using a single `docker-compose up` command,
**so that** I don't need to manage a Python environment, Ollama, or Whisper separately — just a compose file.

**Acceptance criteria:**
- [ ] `docker-compose.yml` defines two services: `rpgwatcher` (the bot) and `ollama`
- [ ] The `rpgwatcher` image is available at `ghcr.io/3d-tech-solutions/rpgwatcher:<version>`
- [ ] All configuration is passed via environment variables in `docker-compose.yml`; no file edits inside the container required
- [ ] The Obsidian vault directory is mounted as a bind mount so notes appear on the host machine
- [ ] `docker compose up -d` on a machine with Docker installed and a valid `.env` file produces a running, functional bot

**Milestone:** v0.8

---

### US-027 — Upgrade to a new version

**As a** GM (Sam),
**I want to** upgrade RPG Watcher to a new version without losing my configuration, session history, or character registry,
**so that** I can benefit from new features without having to re-set-up from scratch.

**Acceptance criteria:**
- [ ] `CHANGELOG.md` clearly describes breaking changes, if any, for each release
- [ ] Database schema migrations are applied automatically on startup (e.g. via `alembic` or a simple migration runner)
- [ ] No configuration keys in `.env` are silently dropped; unrecognised keys produce a startup warning
- [ ] Docker upgrade path is documented: `docker compose pull && docker compose up -d`
- [ ] pip upgrade path is documented: `pip install --upgrade rpgwatcher`

**Milestone:** v0.8

---

## Documentation & Polish

### US-028 — New user follows setup guide start to finish

**As a** GM (Sam),
**I want to** follow a single "First Time Setup" guide that takes me from zero to a completed session note,
**so that** I don't have to piece together information from multiple README sections, ADRs, and source comments.

**Acceptance criteria:**
- [ ] Guide covers in order: prerequisites (Python, Ollama, Discord bot application), installation, `.env` configuration, bot invite, first `/watch` → `/unwatch` cycle, finding the note in Obsidian
- [ ] Each step includes the exact command to run (copy-pasteable)
- [ ] Guide has a "What just happened?" callout after the first successful session explaining the pipeline
- [ ] Guide is linked from the main `README.md` and from the MkDocs site navigation

**Milestone:** v0.9

---

### US-029 — Troubleshoot whisper.cpp not working

**As a** GM (Sam),
**I want to** find a troubleshooting guide that lists the most common `whisper.cpp` failure modes and their fixes,
**so that** I don't have to dig through GitHub issues to figure out why my transcription is returning empty results.

**Acceptance criteria:**
- [ ] Troubleshooting guide includes at minimum: binary path not found, model file not found, `--output-txt -` writing to file named `-` instead of stdout, binary named `main` vs `whisper-cli`, permission denied on binary
- [ ] Each failure mode includes: symptom (what the user sees in Discord), diagnosis (what log line to look for), fix (exact command or config change)
- [ ] Guide links to the relevant section of `docs/research/whisper-backends.md` for background
- [ ] Guide is accessible from the MkDocs site under "Troubleshooting"

**Milestone:** v0.9
**Notes:** The model path bug and `--output-txt -` bug are documented in whisper-backends.md Q4 and Q5.

---

### US-030 — Configuration is stable across the v1.0 API surface

**As a** GM (Sam),
**I want to** know which command names, env-var names, and note schema fields are guaranteed not to change in future minor versions,
**so that** I can build scripts or Obsidian templates that depend on them without fear of breakage.

**Acceptance criteria:**
- [ ] A "Public API" section in the docs explicitly lists: slash command names, all `SCREAMING_SNAKE_CASE` env vars, Obsidian note YAML front-matter keys, and the Python module public functions
- [ ] Any future change to a listed item requires a major version bump (v2.0)
- [ ] `CHANGELOG.md` labels changes as `[API]` when they touch the declared public surface
- [ ] Breaking changes require a migration guide

**Milestone:** v1.0

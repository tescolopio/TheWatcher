# User Stories — v2.0 Standalone Application Track

Stories covering the v1.1 platform abstraction through the v2.0 standalone application release.
See [index.md](index.md) for personas and the ID system.

These stories begin after v1.0 ships.  They represent TheWatcher's evolution from a Discord-first bot into a universal session companion that works for any group, on any voice platform, without requiring Discord at all.

---

## Platform Abstraction (v1.1)

### US-100 — Process an existing recording file from the command line

**As a** GM (Morgan, the Archivist),
**I want to** run `thewatcher process session.wav` on an existing audio file and receive a structured session note,
**so that** I can retroactively generate notes for every prior session I recorded but never processed.

**Acceptance criteria:**
- [ ] `thewatcher process <file>` CLI command accepts a `.wav`, `.mp3`, or `.ogg` file path
- [ ] Full pipeline runs: transcription → LLM summarisation → note written to configured output adapter
- [ ] Progress is shown in the terminal (not Discord) with stage labels and elapsed time
- [ ] `--output <path>` flag overrides the configured output adapter for a single run (writes to a specific file)
- [ ] `--model <name>` flag overrides `OLLAMA_MODEL` for this run
- [ ] Command exits with code 0 on success, non-zero on any pipeline failure, with a human-readable error message
- [ ] Works without the Discord bot running at all

**Milestone:** v1.1

---

### US-101 — Process a multi-track recording with known speakers

**As a** GM (Morgan),
**I want to** process a multi-track recording (e.g. one WAV per participant from Craig or Zencastr) and have each track attributed to the correct character,
**so that** even retroactively processed sessions get speaker-attributed transcripts.

**Acceptance criteria:**
- [ ] `thewatcher process --tracks "player1.wav:Theron Ashveil" "player2.wav:Mira" "gm.wav:Narrator"` accepts multiple labelled files
- [ ] Each track is transcribed separately; results are timestamp-sorted and merged into one labelled transcript
- [ ] Speaker labels appear in the note exactly as provided on the command line
- [ ] A single unlabelled file processes as "Unknown Speaker" with no error

**Milestone:** v1.1

---

### US-102 — Developer adds a custom audio source without modifying core code

**As a** developer,
**I want to** implement the `AudioSource` protocol in my own module and register it with TheWatcher,
**so that** I can add support for a new voice platform (e.g. TeamSpeak, Mumble) without forking the project.

**Acceptance criteria:**
- [ ] `AudioSource` is a `typing.Protocol` with documented methods: `async start()`, `async stop() -> dict[str | int, AudioData]`
- [ ] A third-party package can register an `AudioSource` implementation via a `thewatcher.audio_sources` entry point in `pyproject.toml`
- [ ] The Web UI (v1.2) automatically discovers and lists registered sources in its source selector
- [ ] Official sources (`DiscordSource`, `FileUploadSource`, `SystemMicSource`) are themselves implemented against the same interface — no internal shortcuts

**Milestone:** v1.1
**Notes:** Entry point discovery pattern matches how pytest plugins work.  Keeps the core lean while enabling community extensions.

---

### US-103 — Developer adds a custom output adapter

**As a** developer,
**I want to** implement the `OutputAdapter` protocol to send session notes to a custom destination (e.g. a self-hosted wiki),
**so that** I can integrate TheWatcher with my group's existing tooling.

**Acceptance criteria:**
- [ ] `OutputAdapter` is a `typing.Protocol` with: `async write(note: SessionNote) -> str` (returns a URL or path to the written note)
- [ ] Third-party adapters register via a `thewatcher.output_adapters` entry point
- [ ] `OUTPUT_ADAPTERS` env var (comma-separated) activates multiple adapters simultaneously (fan-out)
- [ ] If one adapter fails, the others still run; the failure is reported but does not block other outputs
- [ ] `ObsidianAdapter` and all other official adapters implement the same interface

**Milestone:** v1.1

---

## Local Web UI & Session Dashboard (v1.2)

### US-104 — View all sessions in a browser

**As a** GM (Sam or River),
**I want to** open a browser to `localhost:7432` and see a list of all recorded sessions with their status, date, and duration,
**so that** I have a single place to manage and review everything TheWatcher has captured.

**Acceptance criteria:**
- [ ] Dashboard lists sessions in reverse chronological order
- [ ] Each session row shows: date, duration, status (recording / processing / done / failed / interrupted), number of speakers, campaign name
- [ ] Clicking a session opens the session detail view (US-105)
- [ ] Sessions can be filtered by campaign and by status
- [ ] Dashboard is accessible from any device on the local network (not just localhost) when bound to `0.0.0.0`
- [ ] Page loads in under 2 seconds for a library of 100 sessions

**Milestone:** v1.2

---

### US-105 — Review the full transcript and summary for a session

**As a** player (Alex or River),
**I want to** read the complete transcript and summary for any past session in my browser,
**so that** I can catch up on a session I missed without having to open Obsidian or scroll through Discord.

**Acceptance criteria:**
- [ ] Session detail page shows: session title, date, duration, campaign, list of speakers
- [ ] Summary section renders as formatted Markdown (all five required sections visible)
- [ ] Transcript section shows speaker-labelled lines in chronological order
- [ ] An audio player is available if the WAV file is still on disk (HTML5 `<audio>`)
- [ ] "Open in Obsidian" link uses the same `obsidian://` deep link as the Discord bot (US-013)
- [ ] Page is readable on mobile browsers

**Milestone:** v1.2

---

### US-106 — Start and stop a recording from the browser

**As a** GM (River),
**I want to** click "Start Recording" in the web UI and control the session without using Discord at all,
**so that** I can use TheWatcher for sessions on other platforms where I'm not using Discord.

**Acceptance criteria:**
- [ ] "New Session" button in the dashboard opens a session setup dialog: audio source selector, campaign selector, session title
- [ ] "Start Recording" button starts the active audio source and shows a live session status (elapsed time, active speakers)
- [ ] "Stop & Process" button stops recording and shows the same pipeline progress stages as the Discord bot (US-012)
- [ ] The web UI and Discord bot can both control the same session (e.g. start via Discord, stop via browser)
- [ ] At most one session per server/instance can be in the `recording` state at a time

**Milestone:** v1.2

---

### US-107 — Access the session dashboard from another device on the home network

**As a** GM (Sam),
**I want to** open the TheWatcher dashboard on my tablet while my bot runs on my home server,
**so that** I can monitor sessions and review notes without being at my server machine.

**Acceptance criteria:**
- [ ] Web server binds to `0.0.0.0` when `WEB_BIND_HOST=0.0.0.0` is set (default: `127.0.0.1` for security)
- [ ] `WEB_PORT` env var controls the port (default: 7432)
- [ ] Documentation includes a short "LAN access" section with the env vars to change and a note about firewall configuration
- [ ] Optional: documentation mentions Tailscale as a zero-config remote-access option for non-LAN use

**Milestone:** v1.2

---

## Extended Audio Sources (v1.3)

### US-108 — Record a session played over Zoom or Google Meet using system audio

**As a** non-Discord user (River),
**I want to** start TheWatcher's loopback capture before the Zoom call and have it record everything played through my speakers,
**so that** I get the same session notes my Discord-using friends get, with no extra software installed.

**Acceptance criteria:**
- [ ] TheWatcher detects available loopback devices (WASAPI loopback on Windows, BlackHole on macOS if installed, PulseAudio monitor on Linux) and lists them in the source selector
- [ ] Web UI shows a dropdown of available audio devices with their type (input / loopback)
- [ ] Loopback captures the mixed system audio; speaker separation uses voice profile matching (US-112)
- [ ] If no voice profiles are enrolled, output is a single "Mixed" speaker label rather than crashing
- [ ] Setup guide includes platform-specific instructions for enabling loopback (Windows: no driver needed; macOS: install BlackHole; Linux: PulseAudio monitor source)

**Milestone:** v1.3

---

### US-109 — Record an in-person session using a laptop microphone

**As a** GM (River),
**I want to** place my laptop in the middle of the table, click "Start Recording", and have TheWatcher capture the whole session from the room mic,
**so that** groups that play face-to-face get the same quality session notes.

**Acceptance criteria:**
- [ ] `SystemMicSource` lists all available input devices on the machine and lets the user select one
- [ ] Silero VAD is applied to the microphone feed to segment speech from silence in real time
- [ ] Speaker diarization using enrolled voice profiles (US-112) attributes each utterance to the nearest matching speaker
- [ ] If only one person is enrolled (or no one is), all speech is captured as "Unknown Speaker" — recording never fails due to missing profiles
- [ ] A "mic test" button in the Web UI records 5 seconds and plays it back before the session starts

**Milestone:** v1.3

---

### US-110 — Upload a multi-track file from a recording platform

**As a** GM (Morgan),
**I want to** upload a `.zip` containing per-participant `.ogg` files from Craig or a multi-track project from Zencastr,
**so that** I can process sessions that were captured by another tool rather than by TheWatcher directly.

**Acceptance criteria:**
- [ ] Web UI "New Session → Audio Source: File Upload" accepts a single file (WAV, MP3, OGG) or a ZIP
- [ ] ZIP is inspected for audio files; each file found is treated as one speaker track
- [ ] File names are used as the default speaker labels (e.g. `alex.ogg` → speaker "alex")  
- [ ] Tracks can be relabelled in the upload dialog before processing begins
- [ ] Correctly handles Craig's naming convention (`<server-id>-<user-id>.ogg`)
- [ ] Unsupported file types in the ZIP are silently skipped (a log warning is emitted)

**Milestone:** v1.3

---

### US-111 — Process a recording from a saved Zoom meeting

**As a** GM (Morgan),
**I want to** import a Zoom local recording folder and have TheWatcher process the audio tracks into a session note,
**so that** even platform-recorded meetings from before TheWatcher was installed can become searchable notes.

**Acceptance criteria:**
- [ ] Zoom local recordings include `audio_only.m4a` (mixed) and optionally per-participant `.m4a` in a subfolder; TheWatcher uses per-participant files when available
- [ ] Zoom's naming convention (`Recording 2026-03-04 19-32-00`) is parsed to pre-fill the session title and date
- [ ] `ffmpeg` (or PyAV) is used for `.m4a` decoding — dependency documented
- [ ] File picker in the Web UI accepts `.m4a` in addition to WAV/MP3/OGG

**Milestone:** v1.3

---

## Voice Profile Enrollment (v1.3 / spans v0.5 foundation)

### US-112 — Enroll a voice profile

**As a** player (Alex or River),
**I want to** record a short voice sample so TheWatcher can recognise my voice in future sessions,
**so that** mixed audio sources (mic, loopback) label my speech with my character name rather than "Unknown Speaker".

**Acceptance criteria:**
- [ ] Web UI "Profile → Enroll Voice" prompts the user to speak three short phrases (~10 seconds total)
- [ ] The enrollment recording is processed into a speaker embedding vector and stored locally, associated with the user's display name and character name
- [ ] Enrollment requires no internet connection
- [ ] Enrollment can be updated at any time; the new embedding replaces the old one
- [ ] A `/enroll` command is available in Discord for Discord-based users (v0.5+)

**Milestone:** v1.3

---

### US-113 — Voice profile improves accuracy over multiple sessions

**As a** GM (Sam),
**I want to** trust that the voice profile matching gets more reliable over time without requiring re-enrollment,
**so that** the system earns its accuracy rather than needing regular manual maintenance.

**Acceptance criteria:**
- [ ] After each session, speaker embeddings from each attributed utterance are averaged into the running centroid for that speaker profile
- [ ] The centroid update uses a weighted average (recent embeddings weighted more heavily) to handle voice changes over time
- [ ] A "profile confidence" indicator in the Web UI shows how many sessions have contributed to each profile
- [ ] Profiles with fewer than 3 sessions are marked as "building" in the UI; users are informed that confidence is still low
- [ ] Centroid update is performed in the background after the session pipeline completes, not blocking the note-write step

**Milestone:** v1.3

---

### US-114 — New player joins mid-campaign

**As a** GM (Sam),
**I want to** add a new player's voice profile quickly before a session starts,
**so that** their first session is already speaker-attributed rather than appearing as "Unknown Speaker" in the notes.

**Acceptance criteria:**
- [ ] Voice enrollment (US-112) can be completed in under 2 minutes (3 prompted phrases + processing)
- [ ] Enrollment is available during a session setup flow ("Who's playing tonight?" → "Add new player → Enroll voice")
- [ ] If a player joins a Discord session without a voice profile, their Discord `user_id` is still used for attribution; the prompt to enroll is shown after the session ends
- [ ] A late enrollment (after one "Unknown Speaker" session) can be retroactively matched against stored embeddings from previous sessions to back-fill their label

**Milestone:** v1.3

---

## Output Adapters (v1.4)

### US-115 — Write session notes to Markdown files without Obsidian

**As a** GM (River),
**I want to** have TheWatcher write plain Markdown files to a directory on my computer rather than requiring an Obsidian vault,
**so that** I can use TheWatcher without adopting a new note-taking application.

**Acceptance criteria:**
- [ ] `OUTPUT_ADAPTERS=markdown` writes `.md` files to `NOTES_DIR` (default: `~/TheWatcher/notes/`)
- [ ] File naming and YAML front-matter are identical to the Obsidian adapter
- [ ] No Obsidian-specific vault structure, `.obsidian/` folder, or plugin dependency is created
- [ ] The "Open in Obsidian" button is hidden when the active adapter is `markdown` (not `obsidian`)

**Milestone:** v1.4

---

### US-116 — Send session notes to a Notion database

**As a** campaign manager (Casey),
**I want to** have each session note automatically appear as a new page in my campaign's Notion database,
**so that** the whole group can access and comment on the notes without needing Obsidian.

**Acceptance criteria:**
- [ ] `OUTPUT_ADAPTERS=notion` activates the Notion adapter; requires `NOTION_API_TOKEN` and `NOTION_DATABASE_ID` env vars
- [ ] A new Notion page is created per session with: title, date, campaign, session summary as page body, speakers list as a multi-select property
- [ ] If the Notion API call fails (rate limit, auth error, network), the failure is logged and the Obsidian/Markdown adapter output is retained as a fallback
- [ ] No Notion API credentials are ever bundled, defaulted, or logged
- [ ] Setup guide explains how to create a Notion integration and share a database with it

**Milestone:** v1.4

---

### US-117 — Receive session notes via a webhook

**As a** developer,
**I want to** configure a webhook URL so that TheWatcher POSTs a JSON payload after each session,
**so that** I can integrate session notes into any custom downstream system without adding code to TheWatcher.

**Acceptance criteria:**
- [ ] `OUTPUT_ADAPTERS=webhook` with `WEBHOOK_URL` set POSTs `{ session_id, title, date, campaign, transcript, summary, speakers: [{name, character}] }` as JSON
- [ ] `WEBHOOK_SECRET` env var, if set, adds an `X-TheWatcher-Signature` HMAC-SHA256 header for receiver verification
- [ ] Failed webhook calls (non-2xx response, timeout) are retried up to 3 times with exponential back-off
- [ ] Payload schema is documented and versioned; breaking schema changes require a major version bump

**Milestone:** v1.4

---

### US-118 — Export a session as a PDF

**As a** GM (Sam),
**I want to** generate a clean PDF of a session's notes from the Web UI,
**so that** I can print it for a player who prefers paper, or archive it outside a note-taking application.

**Acceptance criteria:**
- [ ] "Export → PDF" button on the session detail page (US-105) generates a PDF version of the note
- [ ] PDF uses a clean, readable layout with the campaign name, session title, and date in the header
- [ ] All five summary sections and the full transcript are included
- [ ] Generation uses `pandoc` or `weasyprint`; the dependency is optional and a clear error is shown if it is not installed
- [ ] PDF is offered as a browser download (not emailed or stored server-side)

**Milestone:** v1.4

---

## Standalone Application (v2.0)

### US-119 — Install TheWatcher on Windows with no technical knowledge

**As a** non-Discord user (River),
**I want to** download a `.exe` installer and have TheWatcher running with a browser dashboard in 5 minutes,
**so that** I can use it for my group even though I have never installed a Python application before.

**Acceptance criteria:**
- [ ] A `.exe` installer is available on the GitHub Releases page
- [ ] Installer bundles Python, faster-whisper, and the web UI; no separate dependency installation required
- [ ] On first run, a browser window opens automatically to the first-run wizard (US-120)
- [ ] Installer creates a Start Menu shortcut and a system tray icon
- [ ] Uninstaller cleanly removes all TheWatcher files but prompts to keep notes and session data
- [ ] Equivalent `.dmg` for macOS and `.AppImage` for Linux ship in the same release

**Milestone:** v2.0

---

### US-120 — Complete first-run setup wizard

**As a** non-Discord user (River),
**I want to** be guided through the initial setup in my browser step by step,
**so that** I know exactly what to configure before my first session without reading any documentation.

**Acceptance criteria:**
- [ ] Wizard steps in order: (1) Welcome + what TheWatcher does, (2) Ollama check — detects if running, offers install instructions if not, (3) model download (pulls `llama3.1` if not present), (4) audio source selection and mic test, (5) notes output location, (6) enroll first voice profile (optional, can skip), (7) run a 10-second test session end-to-end
- [ ] Each step has a "Why does this matter?" expandable explanation
- [ ] Wizard is re-accessible at any time from Settings → Run Setup Wizard
- [ ] Step 7 (test session) produces a real Markdown note; success confirmation shows the note on screen
- [ ] Wizard can be skipped entirely for users migrating from a v1.x install (settings are pre-filled)

**Milestone:** v2.0

---

### US-121 — Run TheWatcher completely offline after initial setup

**As a** GM (River),
**I want to** use TheWatcher at a cabin with no internet where we play board games and TTRPGs,
**so that** I don't need connectivity to get session notes.

**Acceptance criteria:**
- [ ] After Ollama models and Whisper models are downloaded, all pipeline stages run with no network access
- [ ] TheWatcher checks for updates only on startup and only if the user opts in; update checks never block startup
- [ ] Notion and webhook adapters degrade gracefully offline (queue for later sync with `WEBHOOK_RETRY_ON_RECONNECT=true`)
- [ ] Documentation explicitly states which features require internet (update check, Notion/Google Docs adapters) and which are fully offline

**Milestone:** v2.0

---

### US-122 — Run multiple campaigns from different groups in one installation

**As a** multi-group GM (Quinn),
**I want to** manage three separate ongoing campaigns — each with different players, character registries, and vocabularies — from a single TheWatcher instance,
**so that** I don't need three separate installs or three separate machines.

**Acceptance criteria:**
- [ ] Campaigns are first-class objects in the Web UI: create, rename, archive, delete
- [ ] Each campaign has its own: character registry, vocabulary list, output folder, preferred LLM model, voice profiles
- [ ] "New Session" flow prompts for campaign selection; the selected campaign's config is applied automatically
- [ ] Campaign archive hides a campaign from the "active" list but preserves all its sessions and notes
- [ ] Switching campaigns between sessions requires no restart or config file edit

**Milestone:** v2.0

---

### US-123 — Auto-update to a new version

**As a** non-technical user (River),
**I want to** be notified in the Web UI when a new version of TheWatcher is available and update it from there,
**so that** I benefit from improvements and fixes without needing to use a terminal or package manager.

**Acceptance criteria:**
- [ ] On startup, TheWatcher checks GitHub Releases for a newer version (opt-in; default on; can disable via `AUTO_UPDATE_CHECK=false`)
- [ ] A non-intrusive banner in the Web UI shows "Version X.Y.Z is available — Release notes | Update now"
- [ ] "Update now" downloads the new installer/package, prompts for confirmation, applies the update, and restarts
- [ ] An active recording is never interrupted by an update; the update is deferred until no session is in progress
- [ ] All session data, configuration, and notes survive the update (migrated as in US-027)

**Milestone:** v2.0

---

### US-124 — Solo player keeps a voice journal

**As a** solo player (Taylor),
**I want to** speak my session journal out loud and have TheWatcher transcribe and format it into a structured note,
**so that** I have a readable record of my solo campaign without typing anything.

**Acceptance criteria:**
- [ ] Mic capture source works with a single enrolled speaker with no group setup required
- [ ] The LLM system prompt has a "solo journal" mode (activated via a session type selector) that adjusts the summary structure: replaces "Player Decisions" with "My Decisions", removes "Party Members Present"
- [ ] LLM processes single-speaker audio correctly (no "Unknown Speaker" entries in a solo session)
- [ ] The note can be routed to any output adapter (Obsidian, Markdown, Notion)
- [ ] Solo mode is accessible directly from the homescreen without requiring campaign setup

**Milestone:** v2.0

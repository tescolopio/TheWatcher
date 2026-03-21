# Privacy Policy

**Last updated:** March 5, 2026

---

## 1. Who This Document Is For

RPG Watcher is **self-hosted, open-source software**. This document describes the privacy properties of the Software itself as published by **3D Tech Solutions**.

Because every deployment is independently operated, there are two privacy relationships you should be aware of:

| Relationship | Who handles your data |
|---|---|
| **You → 3D Tech Solutions** | 3D Tech Solutions does **not** collect, process, or store any of your data. The Software runs entirely on infrastructure you control. |
| **You → the Operator** | The person or team who deployed the bot you are interacting with. They control what is stored and for how long. Contact them for their specific privacy practices. |

If you *are* the Operator, this document applies to your deployment and should inform the privacy notice you provide to your own users.

---

## 2. Core Privacy Architecture

RPG Watcher is designed from the ground up to keep all data on your own hardware:

```
Discord Voice Channel
        │  (voice data transmitted via Discord's infrastructure)
        ▼
Your Bot Instance   ──►  Local Whisper  ──►  Local Ollama  ──►  Your Obsidian Vault
(your machine)                                (your machine)       (your machine)
```

**No audio, transcript, or summary is ever sent to 3D Tech Solutions or any third-party cloud service.** All processing happens locally on the machine running the bot.

---

## 3. What Data the Bot Processes

### 3.1 Voice Audio

- **What:** Raw PCM audio captured from all speakers in a Discord voice channel during an active recording session (between `/watch` and `/unwatch`).
- **How it is stored:** Mixed into a single WAV file on disk in `RECORDINGS_DIR` (default: `/tmp/thewatcher_recordings`). Per-speaker WAV files are also written temporarily when character names are registered.
- **Retention:** Files remain on disk until the Operator manually deletes them or clears the directory. The Software does not automatically delete audio files.

### 3.2 Transcripts

- **What:** Plain-text transcription of the recorded audio, produced by Whisper running locally.
- **How it is stored:** Written to the SQLite database (`RPG_WATCHER_DB`) and optionally embedded in the Obsidian note.
- **Retention:** Persists in the database until the Operator deletes the database file or individual rows.

### 3.3 Session Summaries

- **What:** A structured Markdown summary of the session produced by Ollama running locally.
- **How it is stored:** Written as a `.md` file in the Obsidian vault (`OBSIDIAN_VAULT_PATH/OBSIDIAN_NOTES_FOLDER/`) and stored in the SQLite database.
- **Retention:** Persists until the Operator deletes the note or database entry.

### 3.4 Session Metadata

- **What:** The SQLite database (`rpg-watcher.db`) stores session records including:
  - Guild ID, voice channel name, text channel ID
  - Session start/end timestamps and status
  - File paths to WAV and note files
  - Campaign name (if set via `/campaign set`)
  - Discord user IDs mapped to character names (via `/character set`)
- **Retention:** Persists until the Operator deletes or resets the database.

### 3.5 Discord User IDs

- **What:** Discord user IDs are stored in the character registry when a user runs `/character set`. No other personally identifiable information (display names, email addresses, etc.) is stored by the Software.
- **How it is stored:** In the SQLite database, keyed by guild ID and user ID.
- **Removal:** A user can remove their own registration at any time with `/character clear`. Operators can remove any entry via database access or by implementing additional tooling.

---

## 4. What Data Is NOT Collected

3D Tech Solutions collects **none** of the following:

- Voice audio or recordings
- Transcripts or summaries
- Discord user identities, display names, or email addresses
- Usage analytics or telemetry
- IP addresses or device identifiers
- Crash reports or error logs

The Software contains no analytics library, tracking pixel, or telemetry endpoint.

---

## 5. Third-Party Services

The Software integrates with services that the Operator configures and controls:

| Service | Role | Data sent to it |
|---|---|---|
| **Discord** | Voice data transport and bot commands | Voice audio is transmitted through Discord's infrastructure to reach the bot. Discord's own [Privacy Policy](https://discord.com/privacy) governs this. |
| **Ollama** (local) | LLM inference for session summaries | The plain-text transcript is sent to the Ollama process running on the Operator's machine. If the Operator has configured Ollama to run on a remote host, the transcript travels to that host. |
| **Whisper / whisper.cpp** (local) | Audio transcription | The WAV audio file is processed by Whisper running on the Operator's machine. The audio never leaves that machine unless the Operator explicitly routes it elsewhere. |
| **Obsidian** | Note storage | Notes are written as Markdown files to a directory on the Operator's machine. Obsidian itself is a local application; sync behaviour (e.g. Obsidian Sync, iCloud) is controlled entirely by the Operator. |

3D Tech Solutions has no relationship with, and is not responsible for, the privacy practices of Discord, Ollama, Stability AI, ggerganov, or Obsidian.

---

## 6. Data Security

Security of stored data is the Operator's responsibility. Recommended practices are documented in [SECURITY.md](../SECURITY.md) and include:

- Running the bot as a dedicated low-privilege OS user
- Storing `.env` with `chmod 600` to protect the Discord token
- Pointing `RECORDINGS_DIR` at a directory readable only by the bot process
- Keeping Ollama bound to loopback unless LAN access is specifically needed

---

## 7. Children's Privacy

The Software is not directed at children under 13 (or the applicable age of digital consent in your jurisdiction). Discord itself requires users to be at least 13. Operators should not use the Software in contexts where the voice channel participants are primarily children without appropriate legal basis and parental consent.

---

## 8. User Rights (for Operators to implement)

If you are a User of a third-party deployment, your rights — such as access, rectification, erasure, and portability under GDPR or equivalent legislation — are exercisable against the **Operator**, not 3D Tech Solutions. Contact the person or team who operates the bot instance in your server.

If you are the Operator:

- **Access / Export:** Session data is stored in a standard SQLite database and Markdown files — both are easily readable with standard tools.
- **Erasure:** Delete the relevant rows from `rpg-watcher.db` and the corresponding `.md` and `.wav` files.
- **Character data removal:** Users can run `/character clear` at any time; you can also delete rows from the `characters` table directly.

---

## 9. Changes to This Policy

3D Tech Solutions may update this Policy to reflect changes in the Software. Updates are noted in [CHANGELOG.md](../CHANGELOG.md). The "Last updated" date at the top of this file will change. Operators are responsible for reviewing updates and informing their users of any material changes.

---

## 10. Contact

For questions about this Privacy Policy, open a discussion on the [GitHub repository](https://github.com/tescolopio/rpgwatcher).  
For security vulnerabilities, follow the process described in [SECURITY.md](../SECURITY.md).

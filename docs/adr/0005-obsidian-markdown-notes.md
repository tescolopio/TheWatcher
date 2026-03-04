# ADR-0005 — Obsidian Vault as the Note-taking Target

**Date:** 2026-01-24  
**Status:** Accepted

---

## Context

After the AI summary is generated, it must be persisted somewhere the user can read, search, and link it to other notes.  TheWatcher targets the tabletop RPG community, where players and GMs frequently maintain campaign wikis, session logs, and world-building notes.

The question: what format and application should session notes target?

---

## Decision

Write session notes as **standard Markdown files with YAML front-matter** into an **[Obsidian](https://obsidian.md) vault directory** specified by `OBSIDIAN_VAULT_PATH`.

---

## Rationale

1. **Community fit** — Obsidian is extremely popular in the TTRPG community as a campaign management tool.  Many GMs already use it for session prep, NPC tracking, and world-building.
2. **No proprietary format** — Notes are plain `.md` files.  They are fully readable without Obsidian, portable to any Markdown editor, and version-controllable with git.
3. **Zero API dependency** — Obsidian has no API to call; the integration is simply writing a file to the vault directory.  There is nothing to authenticate, no rate limit, and the note appears in Obsidian the moment the file is written.
4. **YAML front-matter** — Obsidian's Dataview plugin (used widely in the community) can query YAML front-matter fields.  Adding `date`, `tags`, and (in future) `campaign` and `characters` fields makes notes immediately queryable.
5. **Extensibility** — Any future feature (campaign tagging, character lists, session numbering) maps directly to additional YAML fields and Markdown sections.

---

## Alternatives Considered

### Notion

- ❌ Requires a Notion API token; sends content to Notion's cloud
- ❌ Proprietary format; content locked behind the Notion ecosystem
- ❌ Violates ADR-0001

### Logseq

- ✅ Also uses local Markdown files; compatible approach
- ❌ Smaller user base in the TTRPG community vs Obsidian
- ✅ Could be supported as an alternative output path in the future (same file format)

### Plain files in a user-specified directory (no Obsidian assumption)

- ✅ Most generic; works for any user
- ❌ No community resonance; loses the "lands in your vault" value proposition
- The current implementation *is* just writing files to a directory — Obsidian-specific benefits (vault indexing, Dataview) come for free with zero extra code

### SQLite / local database

- ❌ Notes would not be directly readable by humans without a custom UI
- ❌ Not portable; breaks integration with all note-taking tools

---

## Consequences

**Positive:**
- Immediate, zero-configuration integration for existing Obsidian users
- Notes are future-proof plain text; no migration needed if the user switches tools
- YAML front-matter enables advanced Obsidian queries (Dataview, templater, etc.)

**Negative:**
- Users who do not use Obsidian must still set `OBSIDIAN_VAULT_PATH` to an ordinary directory — the bot works, but the "Obsidian" branding in the UX may confuse them
- Obsidian's vault locking behaviour on some platforms may cause write conflicts if Obsidian is performing a sync at the same moment the bot writes (very unlikely in practice; mitigated by the collision-safe filename generator)

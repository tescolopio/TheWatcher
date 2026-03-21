# Security Policy

## Supported Versions

Only the latest release receives security fixes.  Please upgrade before reporting.

| Version | Supported |
|---------|-----------|
| latest  | ✅ Yes    |
| older   | ❌ No     |

---

## Scope

RPG Watcher is a **local-only** bot; by design it makes no outbound network connections except to the two services you configure yourself:

- **Ollama** (`OLLAMA_BASE_URL`) — loopback or LAN only
- **Discord Gateway** — standard Discord bot connection

No audio, transcripts, or summaries are transmitted to any external service.  That said, vulnerabilities in the following areas are in scope:

| Area | Examples |
|------|---------|
| Discord token handling | Token logged, written to world-readable file, exposed in error messages |
| Path traversal | `OBSIDIAN_VAULT_PATH` or `RECORDINGS_DIR` escape to unintended directories |
| Subprocess injection | Unsanitised input passed to `whisper.cpp` subprocess args |
| Privilege escalation | A guild member bypassing the admin-only `/config` gate |
| Dependency vulnerabilities | CVEs in `py-cord`, `ollama`, `openai-whisper`, `python-dotenv`, `PyNaCl` |

Out of scope: vulnerabilities in Discord itself, Ollama, whisper.cpp, or the host operating system.

---

## Reporting a Vulnerability

**Please do not open a public GitHub issue for security vulnerabilities.**

Report privately by one of these methods:

1. **GitHub private security advisory** — go to the repository → Security → Advisories → "Report a vulnerability"
2. **Email** — `security@3dtechsolutions.dev` *(placeholder — update before v1.0)*

Include in your report:

- A clear description of the vulnerability
- Steps to reproduce (or a minimal proof-of-concept)
- The potential impact and attack scenario
- Any suggested mitigations, if you have them

We will acknowledge receipt within **48 hours** and aim to issue a fix or mitigation within **14 days** for critical issues.  We will credit reporters by name (or pseudonym) in the `CHANGELOG.md` and the GitHub advisory unless you prefer to remain anonymous.

---

## Security Hardening Tips for Self-Hosters

- Run the bot as a dedicated low-privilege OS user, **not** as `root`
- Store `.env` with mode `600` (`chmod 600 .env`) so only the bot user can read it
- Point `RECORDINGS_DIR` at a directory that is not world-readable
- Keep Ollama bound to loopback (`127.0.0.1`), not `0.0.0.0`, unless you specifically need LAN access
- Rotate your Discord bot token if you ever accidentally commit or share it

# Terms of Service

**Last updated:** March 5, 2026

---

## 1. Overview

RPG Watcher ("the Software") is a free, open-source self-hosted Discord bot published by **3D Tech Solutions** under the [MIT License](../LICENSE). The Software is made available *as-is* for anyone to run on their own hardware.

Because the Software is self-hosted, **3D Tech Solutions does not operate any service, server, or platform on your behalf**. All responsibilities for a running instance belong to the **Operator** — the individual or entity that deploys and runs the bot — not to 3D Tech Solutions.

These Terms clarify the roles and expectations of everyone involved.

---

## 2. Definitions

| Term | Meaning |
|---|---|
| **Developer** | 3D Tech Solutions, the author and maintainer of the Software |
| **Operator** | You, if you download, self-host, and run an instance of the Software |
| **User** | Any Discord member who interacts with a deployed instance |
| **Software** | The RPG Watcher source code, binaries, Docker images, and documentation |
| **Instance** | A running deployment of the Software operated by an Operator |

---

## 3. License

The Software is distributed under the **MIT License**. You are free to use, copy, modify, merge, publish, and distribute the Software, subject to the conditions of that license. A copy is included in the repository at [LICENSE](../LICENSE).

---

## 4. Operator Responsibilities

By deploying an Instance you agree to:

### 4.1 Comply with Discord's Terms

You must operate the bot in accordance with [Discord's Terms of Service](https://discord.com/terms) and [Developer Policy](https://discord.com/developers/docs/policies-and-agreements/developer-policy). This includes, but is not limited to:

- Not using the bot to mass-harvest user data
- Not automating actions that violate Discord's automation policies
- Keeping your bot token secure and rotating it immediately if compromised

### 4.2 Obtain Participant Consent

**Recording voice audio without the knowledge and consent of all participants may be illegal in your jurisdiction.** Before running `/watch` in any voice channel you must:

- Clearly inform all participants that the session is being recorded
- Obtain their consent where required by applicable law (e.g. California's CCPA, the EU's GDPR, wiretapping laws in two-party consent states/countries)

3D Tech Solutions accepts no liability for unauthorized recordings made using the Software.

### 4.3 Secure Your Instance

You are solely responsible for:

- Protecting your Discord bot token (store it in `.env` with `chmod 600`)
- Securing the machine and network on which the Software runs
- Restricting access to stored audio files, transcripts, and the SQLite database
- Keeping dependencies up to date (see [SECURITY.md](../SECURITY.md))

### 4.4 Respect Your Users

You are the **data controller** for any personal data processed by your Instance. You must provide your own privacy notice to Users explaining how their voice data is recorded, stored, and used.

---

## 5. User Responsibilities

As a User of a third-party Instance:

- You interact with the Software via the Operator's deployment — the Operator, not 3D Tech Solutions, is responsible for that Instance.
- You are bound by the Operator's rules in addition to Discord's Terms of Service.
- You should not use `/watch` or `/preview` to record individuals without their prior knowledge and consent.

---

## 6. No Warranty

The Software is provided **"as is"**, without warranty of any kind, express or implied, including but not limited to the warranties of merchantability, fitness for a particular purpose, and non-infringement.

In no event shall 3D Tech Solutions or any contributor be liable for any claim, damages, or other liability — whether in contract, tort, or otherwise — arising from, out of, or in connection with the Software or the use of it.

This mirrors the warranty disclaimer in the MIT License.

---

## 7. Limitation of Liability

To the maximum extent permitted by applicable law, 3D Tech Solutions shall not be liable for:

- Any loss of data or unauthorized disclosure of recordings
- Non-compliance with recording consent laws by Operators or Users
- Damages arising from third-party services (Discord, Ollama, whisper.cpp) used alongside the Software
- Any indirect, incidental, special, consequential, or punitive damages

---

## 8. Indemnification

If you operate an Instance, you agree to indemnify, defend, and hold harmless 3D Tech Solutions and its contributors from any claims, damages, losses, or expenses (including reasonable legal fees) arising out of your use of the Software, your violation of these Terms, or your violation of any applicable law.

---

## 9. Changes to These Terms

3D Tech Solutions may update these Terms from time to time. Changes are noted in [CHANGELOG.md](../CHANGELOG.md) and take effect when the updated file is committed to the repository. Continuing to use the Software after a change constitutes acceptance.

---

## 10. Contact

For questions about these Terms, open a discussion on the [GitHub repository](https://github.com/tescolopio/rpgwatcher).  
For security issues, follow the process described in [SECURITY.md](../SECURITY.md).

# Docker Deployment Guide

This guide covers running TheWatcher using Docker and `docker compose`.  Everything — the bot, Ollama, and persistent storage — runs in containers on your own hardware.  No audio, transcripts, or summaries leave your machine.

---

## Prerequisites

| Requirement | Notes |
|-------------|-------|
| [Docker Engine](https://docs.docker.com/engine/install/) ≥ 24 | Or Docker Desktop ≥ 4.25 |
| [Docker Compose](https://docs.docker.com/compose/install/) plugin v2 | Bundled with Docker Desktop; `docker compose` (no hyphen) |
| 8 GB RAM | Ollama + bot; 16 GB recommended when running larger models |
| 10 GB free disk | Ollama model weights; `mistral` ≈ 4.1 GB |
| NVIDIA GPU *(optional)* | See [GPU acceleration](#gpu-acceleration) below |

---

## Quick Start

### 1. Clone and configure

```bash
git clone https://github.com/tescolopio/TheWatcher.git
cd TheWatcher
cp .env.example .env
```

Edit `.env` and set **at minimum**:

```dotenv
DISCORD_BOT_TOKEN=your_token_here
OBSIDIAN_VAULT_PATH=/absolute/path/to/your/vault   # host path; see note below
```

> **Vault path** — set this to the directory on your *host* machine that contains your Obsidian vault.  The compose file bind-mounts it into the container at `/vault`.  Set `OBSIDIAN_VAULT_PATH=/vault` in `.env` so the bot writes notes there.

### 2. Start the stack

```bash
docker compose up -d
```

This starts two services:

| Service | What it does |
|---------|-------------|
| `thewatcher` | The Discord bot (built from the local `Dockerfile`) |
| `ollama` | Local LLM server — runs `mistral` by default |

### 3. Pull the LLM model

The Ollama container starts empty.  Pull the model once:

```bash
docker compose exec ollama ollama pull mistral
```

Subsequent restarts reuse the cached weights from the `ollama_data` volume.

### 4. Verify the bot is running

```bash
docker compose logs -f thewatcher
```

You should see a JSON log line containing `"logged_in_as": "TheWatcher#1234"`.  The bot should appear online in your Discord server.

---

## Using the Pre-Built Image

Instead of building locally, you can pull the image published to the GitHub Container Registry on every release:

```bash
# Pull a specific version
docker pull ghcr.io/tescolopio/thewatcher:1.0.0

# Or always-latest stable
docker pull ghcr.io/tescolopio/thewatcher:latest
```

To use the pre-built image in `docker-compose.yml`, replace the `build:` block with `image:`:

```yaml
services:
  thewatcher:
    image: ghcr.io/tescolopio/thewatcher:latest
    # remove the build: block
```

---

## Configuration Reference

All configuration is via environment variables.  Set them in `.env` (copied from `.env.example`).

The compose file enforces these container-specific overrides regardless of `.env`:

| Variable | Container default | Description |
|----------|------------------|-------------|
| `OLLAMA_BASE_URL` | `http://ollama:11434` | Internal hostname of the Ollama service |
| `RECORDINGS_DIR` | `/app/recordings` | WAV file storage (named volume) |
| `THEWATCHER_DB` | `/app/data/thewatcher.db` | SQLite database path (named volume) |
| `LOG_FORMAT` | `json` | Structured JSON logging |

Full reference: [configuration.md](../configuration.md)

---

## Persistent Volumes

| Volume | Mounted at | Contains |
|--------|-----------|---------|
| `recordings` | `/app/recordings` | Per-session WAV files |
| `db_data` | `/app/data` | SQLite database (`thewatcher.db`) |
| `ollama_data` | `/root/.ollama` | Ollama model weights |

Volumes survive container restarts and upgrades.  To reset state (⚠️ destructive):

```bash
docker compose down -v    # removes all named volumes
```

---

## Updating TheWatcher

```bash
# Pull the latest image (if using ghcr.io)
docker compose pull thewatcher

# Or rebuild from source
docker compose build thewatcher

# Restart with the new image
docker compose up -d thewatcher
```

The database schema is backward-compatible across minor versions (SQLite `CREATE TABLE IF NOT EXISTS`).  Check `CHANGELOG.md` before updating across major versions.

---

## GPU Acceleration

To run Ollama with an NVIDIA GPU, uncomment the `deploy` block in `docker-compose.yml`:

```yaml
  ollama:
    image: ollama/ollama:latest
    deploy:
      resources:
        reservations:
          devices:
            - capabilities: [gpu]
```

Also ensure the [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html) is installed on the host.

---

## Health Check & Monitoring

Check service health:

```bash
docker compose ps
docker compose logs thewatcher --tail 50
docker compose logs ollama --tail 20
```

The bot's `/status` slash command verifies end-to-end connectivity (Discord ↔ bot ↔ Ollama) from inside Discord without needing shell access.

---

## Troubleshooting

### Bot starts but commands don't appear in Discord

Wait up to 1 hour for Discord's command cache to refresh after the bot first registers slash commands, or kick and re-invite the bot with the same OAuth URL.

### Ollama connection refused

Ensure the `ollama` container is running and the model is pulled:

```bash
docker compose ps ollama
docker compose exec ollama ollama list
```

If the list is empty, run `docker compose exec ollama ollama pull mistral`.

### `No space left on device` during model pull

Ollama model weights are stored in `ollama_data`.  Move the Docker data root to a larger device, or use a bind-mount:

```yaml
volumes:
  ollama_data:
    driver: local
    driver_opts:
      type: none
      o: bind
      device: /mnt/large-disk/ollama_data
```

### Obsidian notes not appearing in vault

Verify `OBSIDIAN_VAULT_PATH` in `.env` is the **host** path to the vault directory (not the container path).  The container mounts it at `/vault`; set `OBSIDIAN_NOTES_FOLDER` to a path under `/vault`.

### Permission denied on `/app/recordings` or `/app/data`

The container runs as the non-root `watcher` user (UID/GID assigned at build time).  Named volumes are automatically owned correctly.  If you use a *bind mount* instead of a named volume, ensure the host directory is writable by the container user:

```bash
sudo chown -R 1000:1000 ./recordings ./data
```

---

## Building for Multiple Architectures

The release pipeline builds `linux/amd64` and `linux/arm64` images.  To build locally for both platforms (requires Docker Buildx with a multi-platform builder):

```bash
docker buildx create --use --name multi-platform
docker buildx build \
  --platform linux/amd64,linux/arm64 \
  --tag thewatcher:local \
  --load \
  .
```

---

## See Also

- [Local deployment (no Docker)](local.md)
- [Configuration reference](../configuration.md)
- [CHANGELOG](../../CHANGELOG.md)

# ── TheWatcher – multi-stage Docker build ─────────────────────────────────────
#
# Stage 1: builder
#   Installs Python wheel dependencies into /install so the final image does
#   not need build-time tools (gcc, pip, etc.)
#
# Stage 2: runner
#   Copies the pre-built packages from the builder stage.
#   Adds ffmpeg for optional audio post-processing.
#   Runs as a non-root user for security.
#
# Usage:
#   docker build -t thewatcher .
#   docker run --env-file .env thewatcher

# ── Stage 1: builder ──────────────────────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /build

# Copy only dependency manifests first (Docker cache layer optimisation).
COPY requirements.txt pyproject.toml ./
COPY src/__init__.py src/

# Install all Python dependencies into an isolated prefix.
RUN pip install --upgrade pip \
 && pip install --prefix /install --no-cache-dir -r requirements.txt

# ── Stage 2: runner ───────────────────────────────────────────────────────────
FROM python:3.12-slim AS runner

# System packages: ffmpeg (optional audio conversion), libopus for voice.
RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg \
        libopus0 \
    && rm -rf /var/lib/apt/lists/*

# Copy pre-built Python packages from the builder stage.
COPY --from=builder /install /usr/local

# Create a non-root system user.
RUN useradd --system --create-home --shell /bin/bash watcher

WORKDIR /app

# Copy the application source.
COPY --chown=watcher:watcher src/ ./src/
COPY --chown=watcher:watcher pyproject.toml ./

# Install the package itself (editable-equivalent; no re-download of deps).
RUN pip install --no-cache-dir --no-deps -e .

# Runtime directories owned by the app user.
RUN mkdir -p /app/data /app/recordings \
 && chown -R watcher:watcher /app/data /app/recordings

USER watcher

# Default environment (overridden via --env-file or docker-compose environment:)
ENV RECORDINGS_DIR=/app/recordings \
    THEWATCHER_DB=/app/data/thewatcher.db \
    LOG_FORMAT=json \
    PYTHONUNBUFFERED=1

CMD ["python", "-m", "src.bot"]

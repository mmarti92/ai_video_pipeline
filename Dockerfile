# ─── Stage 1: base image with system dependencies ────────────────────────────
FROM python:3.12-slim AS base

# ffmpeg is required by moviepy for video encoding
# ca-certificates is required for CockroachDB Cloud TLS (sslmode=verify-full)
RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# ─── Stage 2: install Python dependencies ────────────────────────────────────
FROM base AS deps

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ─── Stage 3: final image ─────────────────────────────────────────────────────
FROM deps AS final

COPY . .

# Drop privileges – run as a non-root user
RUN useradd --no-create-home --shell /usr/sbin/nologin pipeline
USER pipeline

# Default: run one batch of pending jobs and exit.
# Override with CMD or docker run arguments, e.g.:
#   docker run ... --continuous
#   docker run ... --seed AAPL "Apple Analysis"
ENTRYPOINT ["python", "main.py"]

FROM python:3.11-slim

# Install supercronic for in-container cron support
ARG SUPERCRONIC_VERSION=0.2.33
ARG SUPERCRONIC_SHA1SUM=d2f95e284b81d87aca47df3da58a9a71f33d3b66
ARG TARGETARCH

RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates && \
    ARCH=$(uname -m | sed 's/x86_64/amd64/;s/aarch64/arm64/') && \
    curl -fsSL \
        "https://github.com/aptible/supercronic/releases/download/v${SUPERCRONIC_VERSION}/supercronic-linux-${ARCH}" \
        -o /usr/local/bin/supercronic && \
    chmod +x /usr/local/bin/supercronic && \
    apt-get purge -y --auto-remove curl && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Runtime dependencies from uv.lock into /app/.venv, using the image's Python
COPY --from=ghcr.io/astral-sh/uv:0.13.5 /uv /bin/uv
ENV UV_PYTHON_DOWNLOADS=never \
    PATH=/app/.venv/bin:$PATH
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-cache

COPY immich_folder_organizer/ immich_folder_organizer/
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Default config path matches the docker-compose snippet in docs/design.md
ENV CONFIG_FILE=/config/albums.yaml

ENTRYPOINT ["/entrypoint.sh"]

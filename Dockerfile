FROM python:3.13-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ENV DEBIAN_FRONTEND=noninteractive \
    DOCKERMODE=true \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app:/app/shelfmark \
    UV_LINK_MODE=copy \
    PATH=/app/.venv/bin:$PATH \
    DEBIAN_FRONTEND=noninteractive

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libffi-dev \
    xvfb \
    ffmpeg \
    chromium \
    chromium-common \
    python3-tk \
    unrar-free \
    && rm -rf /var/lib/apt/lists/* \
    && ln -sf /usr/bin/unrar-free /usr/bin/unrar

WORKDIR /app

COPY pyproject.toml uv.lock README.md ./
COPY shelfmark/pyproject.toml shelfmark/
# stub package init so hatchling can discover the package for editable install
RUN mkdir -p src/shelfmark_news && touch src/shelfmark_news/__init__.py

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-default-groups

RUN rm -rf \
    /usr/local/bin/pip \
    /usr/local/bin/pip3 \
    /usr/local/bin/pip3.* \
    /usr/local/lib/python*/site-packages/pip \
    /usr/local/lib/python*/site-packages/pip-*.dist-info

COPY shelfmark/ /app/shelfmark/
COPY src/ /app/src/

RUN rm -f /usr/bin/uv /usr/bin/uvx

RUN mkdir -p /downloads /tmp/shelfmark /config /var/log/shelfmark

ENV SERVER_HOST=0.0.0.0 \
    SERVER_PORT=8080 \
    DOWNLOAD_OUTPUT_DIR=/downloads \
    DOWNLOAD_TMP_DIR=/tmp/shelfmark \
    DOWNLOAD_LOG_DIR=/var/log

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/health')" || exit 1

CMD ["python", "-m", "shelfmark_news.main"]
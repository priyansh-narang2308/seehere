# SeeHere backend image: the API, the worker and migrations share it (Task 34).
#
# Includes ffmpeg and Tesseract (system tools, run as processes), Piper TTS as a separate
# GPL-3.0 executable (never imported; see docs/DEPENDENCIES_AND_LICENSES.md), the LJ Speech
# voice (public domain) and the Whisper small.en weights (MIT), so a fresh server needs no
# model downloads at run time.
FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg tesseract-ocr tesseract-ocr-eng ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.8.19 /uv /uvx /usr/local/bin/

WORKDIR /app

# Dependencies first, so code changes reuse this layer.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY alembic.ini ./
COPY migrations ./migrations
COPY src ./src
RUN uv sync --frozen --no-dev

# Piper: its own isolated tool environment, invoked as the `piper` executable.
ENV UV_TOOL_DIR=/opt/uv-tools UV_TOOL_BIN_DIR=/usr/local/bin
RUN uv tool install piper-tts==1.8.0 \
    && uv tool run --from piper-tts==1.8.0 python -m piper.download_voices en_US-ljspeech-medium --download-dir /opt/piper

# Whisper weights, fetched once at build time.
ENV HF_HOME=/opt/hf
RUN /app/.venv/bin/python -c "from faster_whisper import WhisperModel; WhisperModel('small.en', device='cpu', compute_type='int8')"

RUN useradd --system --uid 10001 --home-dir /app seehere \
    && mkdir -p /data/media \
    && chown -R seehere /data/media

ENV PATH="/app/.venv/bin:$PATH" \
    MEDIA_DIR=/data/media \
    PIPER_VOICE_DIR=/opt/piper \
    HF_HUB_OFFLINE=1

USER seehere
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health/live', timeout=4)" || exit 1

CMD ["uvicorn", "seehere.api.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]

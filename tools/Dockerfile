# ============================================================
# AGENT: one-shot CLI (agent-ingest, agent-generate, backup)
# Core deps + tools (faker, python-docx) — no torch
# ============================================================
FROM python:3.12-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev --extra tools
COPY . .
RUN uv sync --frozen --no-dev --extra tools

FROM python:3.12-slim

RUN groupadd --gid 1000 app && \
    useradd --uid 1000 --gid app --shell /bin/bash --create-home app

COPY --from=builder --chown=app:app /app /app

ENV PATH=/app/.venv/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HOME=/home/app \
    RAG_SERVICE_URL=http://rag:8082

USER app
WORKDIR /app

# No CMD — command is specified in compose: agent-ingest list / agent-generate ...

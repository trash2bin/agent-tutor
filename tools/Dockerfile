# ============================================================
# AGENT: one-shot CLI (agent-ingest, agent-generate, backup)
# Core deps + SDK + tools (faker, python-docx) — no torch
# ============================================================
FROM python:3.12-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app
COPY pyproject.toml uv.lock ./
COPY agent-tutor-sdk agent-tutor-sdk/
COPY tools/pyproject.toml tools/
RUN uv sync --frozen --no-install-project --package tools --no-dev
COPY . .
RUN uv sync --frozen --package tools --no-dev

FROM python:3.12-slim

RUN groupadd --gid 1000 app && \
    useradd --uid 1000 --gid app --shell /bin/bash --create-home app

COPY --from=builder --chown=app:app /app/.venv /app/.venv
COPY --from=builder --chown=app:app /app/fixtures /app/fixtures
COPY --from=builder --chown=app:app /app/mcp_server/tools/rag.py /app/mcp_server/tools/rag.py
COPY --from=builder --chown=app:app /app/mcp_server/tools/__init__.py /app/mcp_server/tools/__init__.py
COPY --from=builder --chown=app:app /app/agent-tutor-sdk /app/agent-tutor-sdk
COPY --from=builder --chown=app:app /app/scripts /app/scripts

ENV PATH=/app/.venv/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app \
    HOME=/home/app \
    RAG_SERVICE_URL=http://rag:8082

USER app
WORKDIR /app

# No CMD — command is specified in compose: agent-ingest list / agent-generate ...

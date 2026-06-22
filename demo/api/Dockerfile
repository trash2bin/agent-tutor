# ============================================================
# API server: LiteLLM agent, session history, backlog
# Core deps + litellm — no torch, no chromadb
# ============================================================
FROM python:3.12-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev --extra api
COPY . .
RUN uv sync --frozen --no-dev --extra api

FROM python:3.12-slim

RUN groupadd --gid 1000 app && \
    useradd --uid 1000 --gid app --shell /bin/bash --create-home app

RUN apt-get update && \
    apt-get install --no-install-recommends -y curl ca-certificates && \
    rm -rf /var/lib/apt/lists/*

COPY --from=builder --chown=app:app /app /app

ENV PATH=/app/.venv/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HOME=/home/app \
    DEMO_API_HOST=0.0.0.0 \
    DEMO_API_PORT=8081 \
    MCP_SERVICE_URL=http://mcp:8083/mcp

USER app
WORKDIR /app

EXPOSE 8081

CMD ["python", "-m", "demo.api.server"]

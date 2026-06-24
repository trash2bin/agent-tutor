# ============================================================
# MCP server: FastMCP + tools (DB reader + RAG client)
# Core deps + SDK — no torch, no chromadb
# ============================================================
FROM python:3.12-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app
COPY pyproject.toml uv.lock ./
COPY agent-tutor-sdk agent-tutor-sdk/
COPY mcp_server/pyproject.toml mcp_server/
RUN uv sync --frozen --no-install-project --package mcp_server --no-dev
COPY . .
RUN uv sync --frozen --package mcp_server --no-dev

FROM python:3.12-slim

RUN groupadd --gid 1000 app && \
    useradd --uid 1000 --gid app --shell /bin/bash --create-home app

RUN apt-get update && \
    apt-get install --no-install-recommends -y curl ca-certificates && \
    rm -rf /var/lib/apt/lists/*

COPY --from=builder --chown=app:app /app/.venv /app/.venv
COPY --from=builder --chown=app:app /app/mcp_server /app/mcp_server
COPY --from=builder --chown=app:app /app/agent-tutor-sdk /app/agent-tutor-sdk


ENV PATH=/app/.venv/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HOME=/home/app \
    MCP_HOST=0.0.0.0 \
    MCP_PORT=8083 \
    RAG_SERVICE_URL=http://rag:8082

USER app
WORKDIR /app

EXPOSE 8083

CMD ["python", "-m", "mcp_server.server"]

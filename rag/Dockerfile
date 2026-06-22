# ============================================================
# RAG service: embeddings, ChromaDB, document parsing
# Only image that pulls sentence-transformers → torch
# ============================================================
FROM python:3.12-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev --extra rag
COPY . .
RUN uv sync --frozen --no-dev --extra rag

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
    HF_HOME=/home/app/.cache/huggingface \
    RAG_HOST=0.0.0.0 \
    RAG_PORT=8082

USER app
WORKDIR /app

EXPOSE 8082

CMD ["python", "-m", "rag.service"]

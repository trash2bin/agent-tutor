"""Внутренние модели пайплайна RAG.

Публичные Pydantic-модели переехали в `agent_tutor_sdk.rag.models`.
Здесь остались только внутренние TypedDict'ы, используемые пайплайном.
"""

from __future__ import annotations

from typing import TypedDict

from agent_tutor_sdk.rag.models import (  # noqa: F401
    Document,
    DocumentChunk,
    DocumentImportResult,
    Material,
    RagContext,
    RagSearchResult,
)


class PageDict(TypedDict):
    """Страница документа после парсинга."""

    page: int | None
    text: str


class ChunkDict(TypedDict):
    """Чанк текста с привязкой к странице."""

    page: int | None
    content: str

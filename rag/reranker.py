"""BM25 reranker для RAG — чистый Python, без внешних зависимостей.

Используется в pipeline.search_documents() после dense-поиска (ChromaDB).
Поднимает keyword-точные запросы, которые dense-эмбеддинги могут не дотянуть.
"""

from __future__ import annotations

import math
import re
from typing import List

from agent_tutor_sdk.rag.models import RagSearchResult


class BM25Reranker:
    """Pure-Python BM25 reranker.

    Реализует BM25 Okapi — стандартный вероятностный ранжировщик.
    Не требует rank_bm25 или nltk — работает на regexp-токенизации.
    """

    def __init__(self, k1: float = 1.5, b: float = 0.75) -> None:
        self.k1 = k1
        self.b = b

    def rerank(
        self,
        query: str,
        results: List[RagSearchResult],
    ) -> List[RagSearchResult]:
        """Переранжировать результаты dense-поиска по BM25.

        Args:
            query: поисковый запрос (тот же, что шёл в dense search)
            results: результаты dense-поиска

        Returns:
            Те же результаты, отсортированные по BM25 score (от высокого к низкому).
            Если results ≤ 1, возвращает as-is.
        """
        if not results or len(results) <= 1:
            return results

        query_tokens = self._tokenize(query)
        if not query_tokens:
            return results

        corpus = [self._tokenize(r.content) for r in results]
        scores = self._compute_bm25(query_tokens, corpus)

        rank = sorted(
            zip(results, scores),
            key=lambda x: -x[1],
        )
        return [r for r, _ in rank]

    def rerank_with_scores(
        self,
        query: str,
        results: List[RagSearchResult],
    ) -> List[tuple[RagSearchResult, float]]:
        """rerank + вернуть (RagSearchResult, score).

        Полезно для отладки: видно, насколько BM25 изменил порядок.
        """
        if not results or len(results) <= 1:
            return [(r, 0.0) for r in results]

        query_tokens = self._tokenize(query)
        if not query_tokens:
            return [(r, 0.0) for r in results]

        corpus = [self._tokenize(r.content) for r in results]
        scores = self._compute_bm25(query_tokens, corpus)

        return sorted(
            zip(results, scores),
            key=lambda x: -x[1],
        )

    @staticmethod
    def _tokenize(text: str) -> List[str]:
        """Разбить текст на токены: alphanumeric (включая кириллицу), lowercase."""
        return re.findall(r"[a-zа-яё0-9]+", text.lower())

    @staticmethod
    def _token_frequency(tokens: List[str]) -> dict[str, int]:
        """Частоты токенов в документе."""
        freq: dict[str, int] = {}
        for t in tokens:
            freq[t] = freq.get(t, 0) + 1
        return freq

    def _compute_bm25(
        self,
        query_tokens: List[str],
        corpus: List[List[str]],
    ) -> List[float]:
        """Вычислить BM25 score для каждого документа в корпусе."""
        n_docs = len(corpus)
        avg_dl = sum(len(d) for d in corpus) / n_docs

        # IDF для каждого уникального токена запроса
        unique_q = set(query_tokens)
        idf: dict[str, float] = {}
        for qt in unique_q:
            doc_count = sum(1 for doc in corpus if qt in doc)
            # Стандартная BM25 IDF: избегаем отрицательных значений
            idf[qt] = math.log(1 + (n_docs - doc_count + 0.5) / (doc_count + 0.5))

        # Считаем score для каждого документа
        scores: List[float] = []
        for doc in corpus:
            dl = len(doc)
            if dl == 0:
                scores.append(0.0)
                continue

            tf = self._token_frequency(doc)
            score = 0.0
            for qt in query_tokens:
                qt_tf = tf.get(qt, 0)
                if qt_tf > 0:
                    score += idf.get(qt, 0) * (
                        (qt_tf * (self.k1 + 1))
                        / (qt_tf + self.k1 * (1 - self.b + self.b * dl / avg_dl))
                    )
            scores.append(score)

        return scores

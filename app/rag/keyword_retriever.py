from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from app.core.config import Settings
from app.repositories.knowledge_chunk_repo import KnowledgeChunkRepository

_CJK_RE = re.compile(r"[一-鿿]+")
_TOKEN_RE = re.compile(r"[A-Za-z0-9_+#.-]+|[一-鿿]{2,}")


@dataclass
class RetrievalChunk:
    source: str
    content: str
    score: float
    metadata: dict[str, Any] = field(default_factory=dict)


class KeywordRetriever:
    """基于 MySQL 的关键词检索器。"""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.chunk_repo = KnowledgeChunkRepository(settings)

    def retrieve(self, query: str, top_k: int = 5) -> list[RetrievalChunk]:
        normalized_query = self._normalize_text(query)
        if not normalized_query:
            return []

        base_terms = self._extract_base_terms(normalized_query)
        fallback_terms = self._expand_fallback_terms(base_terms)
        search_terms = self._merge_terms([normalized_query, *base_terms, *fallback_terms])
        candidate_limit = max(top_k, top_k * self.settings.rag_keyword_candidate_multiplier)
        rows = self.chunk_repo.search_keyword_candidates(
            query=normalized_query,
            terms=search_terms,
            limit=candidate_limit,
        )
        if not rows:
            return []

        results: list[RetrievalChunk] = []
        for row in rows:
            score = self._score_row(
                row,
                normalized_query=normalized_query,
                base_terms=base_terms,
                fallback_terms=fallback_terms,
            )
            if score <= 0:
                continue
            source = str(row.get("source_type") or row.get("doc_name") or "keyword")
            metadata = {
                "chunk_id": row.get("chunk_id"),
                "doc_id": row.get("doc_id"),
                "chunk_index": row.get("chunk_index"),
                "source": source,
                "doc_name": row.get("doc_name"),
                "source_path": row.get("source_path"),
                "retrieval_type": "keyword",
                "vector_score": 0.0,
                "keyword_score": score,
                "fusion_score": score,
            }
            results.append(
                RetrievalChunk(
                    source=source,
                    content=str(row.get("chunk_text") or ""),
                    score=score,
                    metadata=metadata,
                )
            )

        results.sort(key=lambda item: item.score, reverse=True)
        return results[:top_k]

    @staticmethod
    def _normalize_text(value: str) -> str:
        return " ".join(value.strip().split())

    def _extract_base_terms(self, query: str) -> list[str]:
        terms = self._merge_terms(_TOKEN_RE.findall(query))
        if terms:
            return terms
        if len(query) >= self.settings.rag_keyword_min_term_length:
            return [query]
        return []

    def _expand_fallback_terms(self, base_terms: list[str]) -> list[str]:
        expanded: list[str] = []
        min_length = max(2, self.settings.rag_keyword_min_term_length)
        for term in base_terms:
            if not _CJK_RE.fullmatch(term) or len(term) <= min_length + 1:
                continue
            for idx in range(0, len(term) - min_length + 1):
                piece = term[idx : idx + min_length]
                if piece not in expanded:
                    expanded.append(piece)
                if len(expanded) >= 8:
                    return expanded
        return expanded

    @staticmethod
    def _merge_terms(terms: list[str]) -> list[str]:
        merged: list[str] = []
        for term in terms:
            cleaned = term.strip()
            if not cleaned or cleaned in merged:
                continue
            merged.append(cleaned)
        return merged

    def _score_row(
        self,
        row: dict[str, Any],
        *,
        normalized_query: str,
        base_terms: list[str],
        fallback_terms: list[str],
    ) -> float:
        chunk_text = self._normalize_text(str(row.get("chunk_text") or "")).casefold()
        doc_name = self._normalize_text(str(row.get("doc_name") or "")).casefold()
        query_text = normalized_query.casefold()

        exact_score = 0.0
        if query_text:
            if query_text in doc_name:
                exact_score = 1.0
            elif query_text in chunk_text:
                exact_score = 0.9

        strong_hits = sum(1 for term in base_terms if term.casefold() in chunk_text or term.casefold() in doc_name)
        doc_hits = sum(1 for term in base_terms if term.casefold() in doc_name)
        fallback_hits = sum(
            1 for term in fallback_terms if term.casefold() in chunk_text or term.casefold() in doc_name
        )

        strong_ratio = strong_hits / len(base_terms) if base_terms else 0.0
        doc_ratio = doc_hits / len(base_terms) if base_terms else 0.0
        fallback_ratio = fallback_hits / len(fallback_terms) if fallback_terms else 0.0

        blended = strong_ratio * 0.75 + doc_ratio * 0.15 + fallback_ratio * 0.1
        return round(min(1.0, max(exact_score, blended)), 4)

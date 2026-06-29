from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.core.config import Settings
from app.rag.keyword_retriever import KeywordRetriever, RetrievalChunk as KeywordRetrievalChunk
from app.rag.vector_retriever import VectorRetriever

_DEFAULT_SOURCE = "知识库"
_HYBRID_BONUS = 0.05


class RetrievalChunk(BaseModel):
    content: str
    source: str
    score: float
    metadata: dict[str, Any] = Field(default_factory=dict)


class HybridRetriever:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.vector = VectorRetriever(settings)
        self.keyword = KeywordRetriever(settings)

    def retrieve(self, query: str, top_k: int = 5) -> list[RetrievalChunk]:
        vector_results = self.vector.retrieve(query, top_k=top_k)
        keyword_results = self.keyword.retrieve(query, top_k=top_k)

        merged: dict[str, RetrievalChunk] = {}
        for item in vector_results:
            chunk = self._build_vector_chunk(item)
            self._merge_chunk(merged, chunk)

        for item in keyword_results:
            chunk = self._build_keyword_chunk(item)
            self._merge_chunk(merged, chunk)

        for key, chunk in list(merged.items()):
            fused = self._finalize_chunk(chunk)
            merged[key] = fused

        return sorted(merged.values(), key=lambda item: item.score, reverse=True)[:top_k]

    def _build_vector_chunk(self, item: dict[str, Any]) -> RetrievalChunk:
        metadata = dict(item.get("metadata") or {})
        source = str(metadata.get("source") or _DEFAULT_SOURCE)
        score = float(item.get("score") or 0.0)
        metadata.update(
            {
                "source": source,
                "retrieval_type": "vector",
                "vector_score": score,
                "keyword_score": 0.0,
                "fusion_score": score,
            }
        )
        return RetrievalChunk(
            content=str(item.get("content") or ""),
            source=source,
            score=score,
            metadata=metadata,
        )

    def _build_keyword_chunk(self, item: KeywordRetrievalChunk) -> RetrievalChunk:
        metadata = dict(item.metadata or {})
        source = str(metadata.get("source") or item.source or _DEFAULT_SOURCE)
        score = float(item.score or 0.0)
        metadata.update(
            {
                "source": source,
                "retrieval_type": metadata.get("retrieval_type", "keyword"),
                "vector_score": float(metadata.get("vector_score", 0.0) or 0.0),
                "keyword_score": float(metadata.get("keyword_score", score) or 0.0),
                "fusion_score": float(metadata.get("fusion_score", score) or 0.0),
            }
        )
        return RetrievalChunk(
            content=item.content,
            source=source,
            score=score,
            metadata=metadata,
        )

    def _merge_chunk(self, merged: dict[str, RetrievalChunk], chunk: RetrievalChunk) -> None:
        key = self._resolve_chunk_key(chunk)
        existing = merged.get(key)
        if existing is None:
            merged[key] = chunk
            return

        metadata = dict(existing.metadata)
        incoming = chunk.metadata
        vector_score = max(
            float(metadata.get("vector_score", 0.0) or 0.0),
            float(incoming.get("vector_score", 0.0) or 0.0),
        )
        keyword_score = max(
            float(metadata.get("keyword_score", 0.0) or 0.0),
            float(incoming.get("keyword_score", 0.0) or 0.0),
        )

        metadata.update(
            {
                "chunk_id": metadata.get("chunk_id") or incoming.get("chunk_id"),
                "doc_id": metadata.get("doc_id") or incoming.get("doc_id"),
                "chunk_index": metadata.get("chunk_index", incoming.get("chunk_index")),
                "source": metadata.get("source") or incoming.get("source") or chunk.source,
                "doc_name": metadata.get("doc_name") or incoming.get("doc_name"),
                "source_path": metadata.get("source_path") or incoming.get("source_path"),
                "vector_score": vector_score,
                "keyword_score": keyword_score,
            }
        )
        if vector_score > 0 and keyword_score > 0:
            metadata["retrieval_type"] = "hybrid"
        elif vector_score > 0:
            metadata["retrieval_type"] = "vector"
        else:
            metadata["retrieval_type"] = "keyword"

        merged[key] = RetrievalChunk(
            content=existing.content if len(existing.content) >= len(chunk.content) else chunk.content,
            source=str(metadata.get("source") or chunk.source),
            score=max(existing.score, chunk.score),
            metadata=metadata,
        )

    def _finalize_chunk(self, chunk: RetrievalChunk) -> RetrievalChunk:
        metadata = dict(chunk.metadata)
        vector_score = float(metadata.get("vector_score", 0.0) or 0.0)
        keyword_score = float(metadata.get("keyword_score", 0.0) or 0.0)
        fusion_score = vector_score * self.settings.rag_vector_weight + keyword_score * self.settings.rag_keyword_weight
        if vector_score > 0 and keyword_score > 0:
            fusion_score = min(1.0, fusion_score + _HYBRID_BONUS)
            metadata["retrieval_type"] = "hybrid"
        elif vector_score > 0:
            metadata["retrieval_type"] = "vector"
        else:
            metadata["retrieval_type"] = "keyword"
        fusion_score = round(fusion_score, 4)
        metadata["fusion_score"] = fusion_score
        return RetrievalChunk(
            content=chunk.content,
            source=str(metadata.get("source") or chunk.source),
            score=fusion_score,
            metadata=metadata,
        )

    @staticmethod
    def _resolve_chunk_key(chunk: RetrievalChunk) -> str:
        metadata = chunk.metadata or {}
        chunk_id = metadata.get("chunk_id")
        if chunk_id:
            return str(chunk_id)
        doc_id = metadata.get("doc_id")
        chunk_index = metadata.get("chunk_index")
        if doc_id is not None and chunk_index is not None:
            return f"{doc_id}:{chunk_index}"
        return chunk.content[:100]

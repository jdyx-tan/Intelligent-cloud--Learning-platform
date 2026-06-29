from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from typing import Any

import redis
from langchain_core.embeddings import Embeddings
from langchain_community.embeddings import DashScopeEmbeddings

from app.core.config import Settings

_CACHE_PREFIX = "AIGC:EMBEDDING:"
_CACHE_TTL_SECONDS = 7 * 24 * 60 * 60


class CachedDashScopeEmbeddings(Embeddings):
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.delegate = DashScopeEmbeddings(
            model=settings.embedding_model,
            dashscope_api_key=settings.embedding_api_key,
        )
        self._redis = self._build_redis_client()

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_single(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed_single(text)

    def _embed_single(self, text: str) -> list[float]:
        normalized = (text or "").strip()
        if not normalized:
            return self.delegate.embed_query("")

        cache_key = self._cache_key(normalized)
        cached = self._read_cache(cache_key)
        if cached is not None:
            return cached

        vector = self.delegate.embed_query(normalized)
        self._write_cache(cache_key, vector)
        return vector

    def _cache_key(self, text: str) -> str:
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
        return f"{_CACHE_PREFIX}{self.settings.embedding_model}:{digest}"

    def _build_redis_client(self) -> redis.Redis | None:
        try:
            url = getattr(self.settings, "redis_url", None)
            if url:
                return redis.Redis.from_url(url, decode_responses=True)
            return redis.Redis(host="127.0.0.1", port=6379, db=0, decode_responses=True)
        except Exception:
            return None

    def _read_cache(self, cache_key: str) -> list[float] | None:
        if self._redis is None:
            return None
        try:
            raw = self._redis.get(cache_key)
            if not raw:
                return None
            data = json.loads(raw)
            if isinstance(data, Sequence):
                return [float(x) for x in data]
        except Exception:
            return None
        return None

    def _write_cache(self, cache_key: str, vector: list[float]) -> None:
        if self._redis is None:
            return
        try:
            self._redis.setex(
                cache_key,
                _CACHE_TTL_SECONDS,
                json.dumps(vector, ensure_ascii=False),
            )
        except Exception:
            return


def build_embedding_model(settings: Settings) -> Embeddings:
    return CachedDashScopeEmbeddings(settings)

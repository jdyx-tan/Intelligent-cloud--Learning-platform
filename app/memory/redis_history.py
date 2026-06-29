from __future__ import annotations

import json
from datetime import datetime
from typing import Any

import redis

from app.core.config import Settings
from app.domain.models import MessageVO


class RedisHistoryStore:
    PREFIX = "CHAT:"
    STOP_PREFIX = "AIGC:STOP:"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._client = self._build_client(settings)

    @staticmethod
    def _build_client(settings: Settings) -> redis.Redis:
        if settings.redis_url:
            return redis.Redis.from_url(settings.redis_url, decode_responses=True)
        return redis.Redis(
            host=settings.redis_host,
            port=settings.redis_port,
            db=settings.redis_db,
            password=settings.redis_password,
            decode_responses=True,
        )

    @classmethod
    def conversation_id(cls, user_id: int, session_id: str) -> str:
        return f"{user_id}_{session_id}"

    @classmethod
    def redis_key(cls, conversation_id: str) -> str:
        return f"{cls.PREFIX}{conversation_id}"

    def append_message(self, conversation_id: str, role: str, content: str, params: dict[str, Any] | None = None) -> None:
        payload = {
            "type": role,
            "content": content,
            "params": params,
            "ts": datetime.now().isoformat(),
        }
        self._client.rpush(self.redis_key(conversation_id), json.dumps(payload, ensure_ascii=False))

    def list_messages(self, conversation_id: str, last_n: int | None = None) -> list[MessageVO]:
        values = self._client.lrange(self.redis_key(conversation_id), 0, -1)
        if last_n and last_n > 0:
            values = values[-last_n:]
        result: list[MessageVO] = []
        for item in values:
            data = json.loads(item)
            result.append(
                MessageVO(
                    type=data.get("type", "ASSISTANT"),
                    content=data.get("content", ""),
                    params=data.get("params"),
                )
            )
        return result

    def stop(self, session_id: str) -> None:
        self._client.setex(f"{self.STOP_PREFIX}{session_id}", 600, "1")

    def clear_stop(self, session_id: str) -> None:
        self._client.delete(f"{self.STOP_PREFIX}{session_id}")

    def is_stopped(self, session_id: str) -> bool:
        return self._client.exists(f"{self.STOP_PREFIX}{session_id}") > 0

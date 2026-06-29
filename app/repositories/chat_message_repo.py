from __future__ import annotations

import json
import uuid
from typing import Any

from sqlalchemy import create_engine, func, text
from sqlalchemy.engine import Engine

from app.core.config import Settings


class ChatMessageRepository:
    def __init__(self, settings: Settings) -> None:
        self.engine: Engine = create_engine(settings.database_url, future=True)

    def _next_message_order(self, session_id: str) -> int:
        sql = text(
            "SELECT COALESCE(MAX(message_order), 0) + 1 AS next_order "
            "FROM chat_message WHERE session_id = :session_id"
        )
        with self.engine.begin() as conn:
            row = conn.execute(sql, {"session_id": session_id}).mappings().first()
            return row["next_order"] if row else 1

    def save_message(
        self,
        session_id: str,
        user_id: int,
        role: str,
        content: str,
        params: dict[str, Any] | None = None,
        model_name: str | None = None,
        token_count: int | None = None,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
    ) -> str:
        message_id = uuid.uuid4().hex
        message_order = self._next_message_order(session_id)
        sql = text(
            """
            INSERT INTO chat_message (message_id, session_id, user_id, role, content,
                params_json, message_order, token_count, input_tokens, output_tokens,
                model_name, status, created_at)
            VALUES (:message_id, :session_id, :user_id, :role, :content,
                :params_json, :message_order, :token_count, :input_tokens, :output_tokens,
                :model_name, 1, NOW())
            """
        )
        with self.engine.begin() as conn:
            conn.execute(
                sql,
                {
                    "message_id": message_id,
                    "session_id": session_id,
                    "user_id": user_id,
                    "role": role,
                    "content": content,
                    "params_json": None if params is None else json.dumps(params, ensure_ascii=False),
                    "message_order": message_order,
                    "token_count": token_count,
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "model_name": model_name,
                },
            )
        return message_id

    def list_messages(
        self, session_id: str, user_id: int
    ) -> list[dict[str, Any]]:
        sql = text(
            """
            SELECT message_id, role, content, params_json, message_order,
                   token_count, input_tokens, output_tokens, model_name, status, created_at
            FROM chat_message
            WHERE session_id = :session_id AND user_id = :user_id AND status = 1
            ORDER BY message_order ASC, created_at ASC
            """
        )
        with self.engine.begin() as conn:
            rows = conn.execute(
                sql, {"session_id": session_id, "user_id": user_id}
            ).mappings().all()
            return [dict(row) for row in rows]

    def get_message_by_id(self, message_id: str) -> dict[str, Any] | None:
        sql = text(
            "SELECT * FROM chat_message WHERE message_id = :message_id"
        )
        with self.engine.begin() as conn:
            row = conn.execute(sql, {"message_id": message_id}).mappings().first()
            return dict(row) if row else None

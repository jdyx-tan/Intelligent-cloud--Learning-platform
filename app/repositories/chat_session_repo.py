from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from app.core.config import Settings


class ChatSessionRepository:
    def __init__(self, settings: Settings) -> None:
        self.engine: Engine = create_engine(settings.database_url, future=True)

    def create_session(
        self, session_id: str, user_id: int, title: str | None = None
    ) -> None:
        sql = text("""
            INSERT INTO chat_session (session_id, user_id, title, summary, status, message_count, last_message_at, create_time, update_time, creater, updater)
            VALUES (:session_id, :user_id, :title, NULL, 1, 0, NOW(), NOW(), NOW(), :user_id, :user_id)
            """)
        with self.engine.begin() as conn:
            conn.execute(
                sql, {"session_id": session_id, "user_id": user_id, "title": title}
            )

    def update_session_summary(self, session_id: str, summary: str) -> None:
        sql = text("""
            UPDATE chat_session
            SET summary = :summary, update_time = NOW()
            WHERE session_id = :session_id
            """)
        with self.engine.begin() as conn:
            conn.execute(sql, {"session_id": session_id, "summary": summary})

    def update_last_message_at(self, session_id: str) -> None:
        sql = text("""
            UPDATE chat_session
            SET last_message_at = NOW(), message_count = message_count + 1, update_time = NOW()
            WHERE session_id = :session_id
            """)
        with self.engine.begin() as conn:
            conn.execute(sql, {"session_id": session_id})

    def list_recent_sessions(
        self, user_id: int, limit: int = 30
    ) -> list[dict[str, Any]]:
        sql = text("""
            SELECT session_id, title, summary, status, message_count, last_message_at, update_time
            FROM chat_session
            WHERE user_id = :user_id AND title IS NOT NULL AND title <> ''
            ORDER BY update_time DESC
            LIMIT :limit
            """)
        with self.engine.begin() as conn:
            rows = (
                conn.execute(sql, {"user_id": user_id, "limit": limit}).mappings().all()
            )
            return [dict(row) for row in rows]

    def touch_session_title(self, session_id: str, user_id: int, title: str) -> None:
        sql = text(
            """
            UPDATE chat_session
            SET title = CASE WHEN title IS NULL OR title = '' THEN :title ELSE title END,
                last_message_at = NOW(),
                message_count = message_count + 1,
                update_time = NOW(),
                updater = :user_id
            WHERE session_id = :session_id AND user_id = :user_id
            """
        )
        with self.engine.begin() as conn:
            conn.execute(
                sql,
                {
                    "session_id": session_id,
                    "user_id": user_id,
                    "title": title[:100],
                },
            )

    @staticmethod
    def group_by_time(records: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
        now = datetime.now()
        grouped: dict[str, list[dict[str, Any]]] = {
            "当天": [],
            "最近30天": [],
            "最近1年": [],
            "1年以上": [],
        }
        for item in records:
            update_time = item.get("update_time")
            if not isinstance(update_time, datetime):
                grouped["1年以上"].append(item)
                continue
            delta = now - update_time
            if delta.days == 0:
                grouped["当天"].append(item)
            elif delta.days <= 30:
                grouped["最近30天"].append(item)
            elif delta.days <= 365:
                grouped["最近1年"].append(item)
            else:
                grouped["1年以上"].append(item)
        return {k: v for k, v in grouped.items() if v}

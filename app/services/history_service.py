from __future__ import annotations

import json

from app.core.config import Settings
from app.domain.models import ChatSessionVO, MessageVO
from app.repositories.chat_message_repo import ChatMessageRepository
from app.repositories.chat_session_repo import ChatSessionRepository


class HistoryService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.message_repo = ChatMessageRepository(settings)
        self.session_repo = ChatSessionRepository(settings)

    def query_messages(self, user_id: int, session_id: str) -> list[MessageVO]:
        rows = self.message_repo.list_messages(session_id=session_id, user_id=user_id)
        result: list[MessageVO] = []

        for row in rows:
            params_json = row.get("params_json")
            params = json.loads(params_json) if params_json else None

            result.append(
                MessageVO(
                    type=row.get("role", "ASSISTANT"),
                    content=row.get("content", ""),
                    params=params,
                )
            )
        return result

    def query_history_sessions(self, user_id: int) -> dict[str, list[ChatSessionVO]]:
        rows = self.session_repo.list_recent_sessions(user_id=user_id)
        grouped = self.session_repo.group_by_time(rows)

        result: dict[str, list[ChatSessionVO]] = {}
        for key, values in grouped.items():
            result[key] = [
                ChatSessionVO(
                    sessionId=item.get("session_id", ""),
                    title=item.get("title"),
                    updateTime=item.get("update_time"),
                )
                for item in values
            ]
        return result

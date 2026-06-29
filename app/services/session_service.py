from __future__ import annotations

import random
import uuid

from app.core.config import Settings
from app.domain.models import SessionExample, SessionVO
from app.repositories.chat_session_repo import ChatSessionRepository
from app.services.prompt_service import PromptService


class SessionService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.prompt_service = PromptService(settings)
        self.repo = ChatSessionRepository(settings)

    def create_session(self, user_id: int, n: int = 3) -> SessionVO:
        title, describe, examples = self.prompt_service.get_session_meta()
        session_id = uuid.uuid4().hex
        chosen = self._pick_examples(examples, n)
        self.repo.create_session(session_id=session_id, user_id=user_id)
        return SessionVO(sessionId=session_id, title=title, describe=describe, examples=chosen)

    def hot_examples(self, n: int = 3) -> list[SessionExample]:
        _, _, examples = self.prompt_service.get_session_meta()
        return self._pick_examples(examples, n)

    @staticmethod
    def _pick_examples(examples: list[SessionExample], n: int) -> list[SessionExample]:
        if not examples:
            return []
        if len(examples) <= n:
            return examples
        return random.sample(examples, n)

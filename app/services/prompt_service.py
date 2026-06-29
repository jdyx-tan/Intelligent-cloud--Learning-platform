from __future__ import annotations

from app.core.config import Settings
from app.core.nacos import NacosClient
from app.domain.models import SessionExample


class PromptService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.nacos = NacosClient(settings)

    def get_text_prompt(self) -> str:
        remote = self.nacos.get_text_config(self.settings.nacos_text_prompt_data_id)
        if remote:
            return remote
        return "你是天机学堂AI助理，请基于用户问题给出清晰、专业、友好的回答。"

    def get_session_meta(self) -> tuple[str, str, list[SessionExample]]:
        examples = [SessionExample(**item) for item in self.settings.session_examples()]
        return self.settings.session_title, self.settings.session_describe, examples

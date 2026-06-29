from __future__ import annotations

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from app.core.config import Settings
from app.domain.models import MessageVO
from app.providers.llm import build_text_model
from app.services.prompt_service import PromptService

_RECENT_LIMIT = 4  # 有摘要时额外拼接最近几轮完整消息


class ChatTextService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.prompt_service = PromptService(settings)
        self.model = build_text_model(settings)

    def chat_text(
        self,
        question: str,
        history: list[MessageVO] | None = None,
        summary: str | None = None,
    ) -> str:
        prompt = self.prompt_service.get_text_prompt()
        messages: list = [SystemMessage(content=prompt)]

        if summary:
            # 有摘要：用摘要兜底 + 最近几轮完整消息
            messages.append(SystemMessage(content=f"以下是对话历史摘要：\n{summary}"))
            if history:
                recent = history[-_RECENT_LIMIT:]
                for msg in recent:
                    if msg.type == "USER":
                        messages.append(HumanMessage(content=msg.content))
                    else:
                        messages.append(AIMessage(content=msg.content))
        elif history:
            # 无摘要但有历史：全部拼上
            for msg in history:
                if msg.type == "USER":
                    messages.append(HumanMessage(content=msg.content))
                else:
                    messages.append(AIMessage(content=msg.content))

        messages.append(HumanMessage(content=question))

        response = self.model.invoke(messages)
        content = response.content
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            return "".join(str(item) for item in content)
        return str(content)

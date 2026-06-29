from __future__ import annotations

from langchain_openai import ChatOpenAI

from app.core.config import Settings


def build_text_model(settings: Settings) -> ChatOpenAI:
    return ChatOpenAI(
        base_url=settings.chat_base_url,
        api_key=settings.chat_api_key,
        model=settings.chat_model,
        temperature=0.7,
    )

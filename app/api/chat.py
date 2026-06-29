from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import PlainTextResponse

from app.core.config import get_settings
from app.core.response import maybe_wrap
from app.domain.models import TemplateVO
from app.services.agent_service import AgentService

router = APIRouter(prefix="/chat", tags=["chat"])
_template = TemplateVO()


@router.post("/text", response_class=PlainTextResponse)
async def chat_text(question: str, request: Request) -> str:
    del request
    agent = AgentService(get_settings())
    return agent.chat(question)


@router.get("/templates")
async def get_templates(request: Request):
    return maybe_wrap(request, _template.model_dump())

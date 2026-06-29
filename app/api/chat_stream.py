from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from app.core.config import get_settings
from app.core.security import get_required_user_id
from app.domain.models import ChatDTO
from app.services.stream_chat_service import StreamChatService

router = APIRouter(prefix="/chat", tags=["chat-stream"])


@router.post("")
async def chat(
    chat_dto: ChatDTO,
    request: Request,
    user_id: int = Depends(get_required_user_id),
):
    del request
    service = StreamChatService(get_settings())
    generator = service.stream_chat(
        user_id=user_id,
        question=chat_dto.question,
        session_id=chat_dto.sessionId,
    )
    return StreamingResponse(generator, media_type="text/event-stream")


@router.post("/stop")
async def stop(sessionId: str):
    service = StreamChatService(get_settings())
    service.stop(sessionId)
    return None

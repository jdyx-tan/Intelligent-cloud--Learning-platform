from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from app.core.config import get_settings
from app.core.response import maybe_wrap
from app.core.security import get_required_user_id
from app.services.history_service import HistoryService

router = APIRouter(prefix="/session", tags=["session-history"])


@router.get("/{sessionId}")
async def query_by_session_id(
      sessionId: str,
      request: Request,
      user_id: int = Depends(get_required_user_id),
  ):
      service = HistoryService(get_settings())
      result = [
          item.model_dump()
          for item in service.query_messages(user_id=user_id, session_id=sessionId)
      ]
      return maybe_wrap(request, result)


@router.get("/history")
async def query_history_session(
      request: Request,
      user_id: int = Depends(get_required_user_id),
  ):
      service = HistoryService(get_settings())
      result = {
          k: [item.model_dump() for item in v]
          for k, v in service.query_history_sessions(user_id=user_id).items()
      }
      return maybe_wrap(request, result)
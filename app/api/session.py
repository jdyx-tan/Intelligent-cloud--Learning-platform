from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request

from app.core.config import get_settings
from app.core.response import maybe_wrap
from app.core.security import get_required_user_id
from app.services.session_service import SessionService

router = APIRouter(prefix="/session", tags=["session"])


@router.post("")
async def create_session(
    request: Request,
    n: int = Query(default=3, alias="n"),
    user_id: int = Depends(get_required_user_id),
):
    service = SessionService(get_settings())
    result = service.create_session(user_id=user_id, n=n)
    return maybe_wrap(request, result.model_dump())


@router.get("/hot")
async def hot_examples(request: Request, n: int = Query(default=3, alias="n")):
    service = SessionService(get_settings())
    result = [item.model_dump() for item in service.hot_examples(n=n)]
    return maybe_wrap(request, result)

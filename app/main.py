from __future__ import annotations

from fastapi import FastAPI

from app.api.chat import router as chat_router
from app.api.chat_stream import router as chat_stream_router
from app.api.document import router as document_router
from app.api.session import router as session_router
from app.api.session_history import router as session_history_router
from app.core.config import get_settings

settings = get_settings()
app = FastAPI(title="Tianji AIGC Python Service", version="0.1.0")

app.include_router(chat_router)
app.include_router(chat_stream_router)
app.include_router(document_router)
app.include_router(session_router)
app.include_router(session_history_router)


@app.get("/health")
def health() -> dict[str, str]:
      return {"status": "ok", "service": settings.app_name}
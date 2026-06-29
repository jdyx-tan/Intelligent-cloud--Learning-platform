from __future__ import annotations

from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse

from app.core.config import get_settings


def maybe_wrap(request: Request, data: Any, status_code: int = 200) -> Any:
    settings = get_settings()
    request_from = request.headers.get("x-request-from", "")
    if settings.response_wrap and request_from.lower() == "gateway":
        return JSONResponse(
            status_code=status_code,
            content={
                "code": status_code,
                "msg": "OK",
                "data": data,
                "requestId": request.headers.get("requestId") or request.headers.get("requestid"),
            },
        )
    return data

from __future__ import annotations

from fastapi import Header, HTTPException, status


async def get_optional_user_id(user_info: str | None = Header(default=None, alias="user-info")) -> int | None:
    if user_info is None or user_info == "":
        return None
    try:
        return int(user_info)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid user-info header") from exc


async def get_required_user_id(user_id: int | None = Header(default=None, alias="user-info")) -> int:
    if user_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="missing user-info header")
    return user_id

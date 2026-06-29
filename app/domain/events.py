
from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class ChatEventVO(BaseModel):
      eventData: Any | None = None
      eventType: int


class ChatEventType:
      DATA = 1001
      STOP = 1002
      PARAM = 1003


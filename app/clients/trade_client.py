from __future__ import annotations

from typing import Any

from app.clients.base import BaseHttpClient
from app.core.config import Settings


class TradeClient(BaseHttpClient):
    """调用 trade-service / tj-trade (port 8088)"""

    def __init__(self, settings: Settings) -> None:
        super().__init__(settings.trade_service_url)

    def pre_place_order(self, course_ids: list[int]) -> dict[str, Any]:
        """GET /orders/prePlaceOrder?courseIds=... - 预下单（确认订单信息）"""
        return self._get("/orders/prePlaceOrder", params={"courseIds": course_ids})

from __future__ import annotations

from functools import lru_cache
from typing import Any

from langchain_core.tools import tool

from app.clients.trade_client import TradeClient
from app.core.config import Settings


@lru_cache
def _settings() -> Settings:
    return Settings()


@tool
def pre_place_order(course_ids: list[int]) -> str:
    """根据课程id列表进行预下单，查询课程价格、可用优惠券等信息。参数 course_ids 是课程ID列表。"""
    settings = _settings()
    client = TradeClient(settings)
    try:
        result = client.pre_place_order(course_ids)
        if not result:
            return "预下单失败，未获取到订单信息。"
        order_id = result.get("orderId", "")
        total_amount = result.get("totalAmount", 0)
        courses = result.get("courses", [])
        lines = [f"预下单成功！订单ID：{order_id}"]
        lines.append(f"总金额：¥{total_amount / 100:.2f}" if isinstance(total_amount, int) else f"总金额：{total_amount}")
        if courses:
            lines.append("课程明细：")
            for c in courses:
                name = c.get("name", "未知课程")
                price = c.get("price", 0)
                price_str = f"¥{price / 100:.2f}" if isinstance(price, int) and price > 0 else "免费"
                lines.append(f"  - {name} {price_str}")
        return "\n".join(lines)
    except Exception as e:
        return f"预下单请求失败：{e}"

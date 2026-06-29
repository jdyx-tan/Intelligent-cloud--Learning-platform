from __future__ import annotations

from functools import lru_cache
from typing import Any

from langchain_core.tools import tool

from app.clients.base import HttpClientError, RemoteServiceError, ServiceUnavailableError
from app.clients.course_client import CourseClient
from app.clients.search_client import SearchClient
from app.core.config import Settings


@lru_cache
def _settings() -> Settings:
    return Settings()


def _fmt_course(c: dict[str, Any]) -> str:
    name = c.get("name", "未知课程")
    price = c.get("price", 0)
    if isinstance(price, int) and price > 0:
        price_str = f"¥{price / 100:.2f}"
    else:
        price_str = "免费"
    teacher = c.get("teacher", c.get("teacherName", "未知讲师"))
    sold = c.get("sold", c.get("enrollNum", 0))
    return f"- 《{name}》 价格：{price_str} 讲师：{teacher} 已报名：{sold}人"


@tool
def query_course_info(course_name: str) -> str:
    """根据课程名称查询课程详情，包括课程介绍、价格、适合人群等信息。"""
    settings = _settings()
    try:
        # 先通过搜索接口查课程id
        search_client = SearchClient(settings)
        ids = search_client.query_course_ids_by_name(course_name)
        if not ids:
            return f"当前未找到与「{course_name}」相关的课程信息，我暂时不清楚更具体的课程详情。"

        # 取第一个结果查详细信息
        course_id = ids[0]
        course_client = CourseClient(settings)
        course = course_client.get_course_by_id(course_id, with_catalogue=False, with_teachers=True)
        if not course:
            return f"当前未找到课程「{course_name}」的详细信息，我暂时不清楚更具体的课程介绍。"

        name = course.get("name", "未知")
        price = course.get("price", 0)
        price_str = f"¥{price / 100:.2f}" if isinstance(price, int) and price > 0 else "免费"
        status = course.get("status", "")
        status_map = {1: "待上架", 2: "已上架", 3: "已下架", 4: "已完结"}
        status_str = status_map.get(status, "未知")
        teachers = course.get("teacherIds", [])
        teacher_str = f", 讲师ID: {teachers}" if teachers else ""

        return (
            f"课程名称：{name}\n"
            f"价格：{price_str}\n"
            f"状态：{status_str}\n"
            f"课程ID：{course_id}{teacher_str}"
        )
    except ServiceUnavailableError:
        return (
            f"课程/搜索服务暂不可用，暂时无法查询「{course_name}」的实时课程详情。"
            "请继续基于已有知识库内容作答，并明确说明当前信息可能不完整。"
        )
    except (RemoteServiceError, HttpClientError) as exc:
        return f"查询课程「{course_name}」时服务出现异常：{exc}。请继续基于已有知识库内容作答。"


@tool
def recommend_courses(keyword: str) -> str:
    """根据关键词搜索推荐相关课程。"""
    settings = _settings()
    try:
        search_client = SearchClient(settings)
        result = search_client.search_courses_portal(keyword=keyword, page=1, size=5)
        items = result.get("list", []) if isinstance(result, dict) else []
        if not items:
            return f"当前未找到与「{keyword}」相关的课程推荐，我暂时不清楚更具体的课程结果。"

        lines = [f"为您推荐与「{keyword}」相关的课程："]
        for c in items:
            lines.append(_fmt_course(c))
        return "\n".join(lines)
    except ServiceUnavailableError:
        return (
            f"课程搜索服务暂不可用，暂时无法获取与「{keyword}」相关的实时课程推荐。"
            "请继续基于已有知识库内容作答，并明确说明当前推荐结果可能不完整。"
        )
    except (RemoteServiceError, HttpClientError) as exc:
        return f"获取与「{keyword}」相关课程推荐时服务出现异常：{exc}。请继续基于已有知识库内容作答。"


@tool
def recommend_best_courses() -> str:
    """推荐精品好课。"""
    settings = _settings()
    try:
        client = SearchClient(settings)
        items = client.query_best_courses()
        if not items:
            return "当前暂无可确认的精品好课推荐，我暂时不清楚更具体的实时推荐结果。"

        lines = ["【精品好课推荐】"]
        for c in items[:5]:
            lines.append(_fmt_course(c))
        return "\n".join(lines)
    except ServiceUnavailableError:
        return "精品课程推荐服务暂不可用，请继续基于已有知识库内容作答，并明确说明当前实时推荐结果不可获取。"
    except (RemoteServiceError, HttpClientError) as exc:
        return f"获取精品课程推荐时服务出现异常：{exc}。请继续基于已有知识库内容作答。"


@tool
def recommend_new_courses() -> str:
    """推荐最新上架的课程。"""
    settings = _settings()
    try:
        client = SearchClient(settings)
        items = client.query_new_courses()
        if not items:
            return "当前暂无可确认的新课推荐，我暂时不清楚更具体的实时上新结果。"

        lines = ["【新课推荐】"]
        for c in items[:5]:
            lines.append(_fmt_course(c))
        return "\n".join(lines)
    except ServiceUnavailableError:
        return "新课推荐服务暂不可用，请继续基于已有知识库内容作答，并明确说明当前实时上新结果不可获取。"
    except (RemoteServiceError, HttpClientError) as exc:
        return f"获取新课推荐时服务出现异常：{exc}。请继续基于已有知识库内容作答。"

from __future__ import annotations

from typing import Any

from app.clients.base import BaseHttpClient
from app.core.config import Settings


class SearchClient(BaseHttpClient):
    """调用 search-service / tj-search (port 8083)"""

    def __init__(self, settings: Settings) -> None:
        super().__init__(settings.search_service_url)

    def query_best_courses(self) -> list[dict[str, Any]]:
        """GET /recommend/best - 精品好课推荐"""
        data = self._get("/recommend/best")
        return data if isinstance(data, list) else []

    def query_new_courses(self) -> list[dict[str, Any]]:
        """GET /recommend/new - 新课推荐"""
        data = self._get("/recommend/new")
        return data if isinstance(data, list) else []

    def query_free_courses(self) -> list[dict[str, Any]]:
        """GET /recommend/free - 精品公开课推荐"""
        data = self._get("/recommend/free")
        return data if isinstance(data, list) else []

    def query_courses_by_category(self, cate_lv2_id: int) -> list[dict[str, Any]]:
        """GET /interests/{id}/courses - 根据二级分类查询课程"""
        data = self._get(f"/interests/{cate_lv2_id}/courses")
        return data if isinstance(data, list) else []

    def search_courses_portal(
        self, keyword: str | None = None, page: int = 1, size: int = 10
    ) -> dict[str, Any]:
        """GET /courses/portal - 用户端课程搜索"""
        params = {"page": page, "size": size}
        if keyword:
            params["keyword"] = keyword
        return self._get("/courses/portal", params=params)

    def query_course_ids_by_name(self, keyword: str) -> list[int]:
        """GET /courses/name?keyword=... - 根据名称搜索课程id"""
        data = self._get("/courses/name", params={"keyword": keyword})
        return data if isinstance(data, list) else []

from __future__ import annotations

from typing import Any

from app.clients.base import BaseHttpClient
from app.core.config import Settings


class CourseClient(BaseHttpClient):
    """调用 course-service / tj-course (port 8086)"""

    def __init__(self, settings: Settings) -> None:
        super().__init__(settings.course_service_url)

    def get_course_by_id(
        self,
        course_id: int,
        with_catalogue: bool = False,
        with_teachers: bool = False,
    ) -> dict[str, Any] | None:
        """GET /course/{id} - 查询课程详细信息"""
        data = self._get(
            f"/course/{course_id}",
            params={"withCatalogue": with_catalogue, "withTeachers": with_teachers},
        )
        return data

    def search_courses_by_name(self, keyword: str) -> list[int]:
        """GET /courses/name - 根据课程名称模糊查询课程id列表"""
        data = self._get("/courses/name", params={"name": keyword})
        return data if isinstance(data, list) else []

    def get_simple_info_list(self, ids: list[int]) -> list[dict[str, Any]]:
        """GET /courses/simpleInfo/list?ids=... - 批量查询课程简单信息"""
        data = self._get("/courses/simpleInfo/list", params={"ids": ids})
        return data if isinstance(data, list) else []

    def get_course_search_info(self, course_id: int) -> dict[str, Any] | None:
        """GET /course/{id}/searchInfo - 查询课程检索信息（用于索引库）"""
        return self._get(f"/course/{course_id}/searchInfo")

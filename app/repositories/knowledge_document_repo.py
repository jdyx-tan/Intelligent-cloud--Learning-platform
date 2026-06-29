from __future__ import annotations

from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from app.core.config import Settings


class KnowledgeDocumentRepository:
    """知识库文档元数据仓库

    操作 knowledge_document 表，提供文档元数据的增删改查。
    文档状态定义：
        0 = 待处理/处理中
        1 = 已成功入库
        2 = 导入失败/禁用
        3 = 已删除（软删除）
    """

    def __init__(self, settings: Settings) -> None:
        """初始化仓库，创建数据库连接

        Args:
            settings: 全局配置对象，包含 database_url 连接串
        """
        self.engine: Engine = create_engine(settings.database_url, future=True)

    def create_document(
        self,
        doc_id: str,
        doc_name: str,
        source_type: str = "manual",
        source_path: str | None = None,
        version: str = "1.0",
        file_hash: str | None = None,
        remark: str | None = None,
    ) -> None:
        """创建文档记录（初始状态为 0 = 待处理）

        Args:
            doc_id:      文档业务唯一标识
            doc_name:    文档名称
            source_type: 文档来源类型（manual / course / pdf / web / …）
            source_path: 原始文件路径或来源地址（可选）
            version:     文档版本号，默认 "1.0"
            file_hash:   文件内容 SHA256 哈希，用于去重和变更检测
            remark:      备注信息（可选）
        """
        sql = text(
            """
            INSERT INTO knowledge_document
                (doc_id, doc_name, source_type, source_path, version, status,
                 priority, file_hash, remark, created_at, updated_at)
            VALUES
                (:doc_id, :doc_name, :source_type, :source_path, :version, 0,
                 0, :file_hash, :remark, NOW(), NOW())
            """
        )
        with self.engine.begin() as conn:
            conn.execute(
                sql,
                {
                    "doc_id": doc_id,
                    "doc_name": doc_name,
                    "source_type": source_type,
                    "source_path": source_path,
                    "version": version,
                    "file_hash": file_hash,
                    "remark": remark,
                },
            )

    def get_by_file_hash(self, file_hash: str) -> dict[str, Any] | None:
        """根据文件哈希查询已有文档（用于去重）

        只查询状态为 0（处理中）或 1（已入库）的文档，
        失败的（2）和已删除的（3）不视为已存在，允许重新导入。
        返回最新的一条记录。

        Args:
            file_hash: 文件内容的 SHA256 哈希

        Returns:
            匹配的文档记录字典，未找到则返回 None
        """
        sql = text(
            """
            SELECT *
            FROM knowledge_document
            WHERE file_hash = :file_hash
              AND status IN (0, 1)
            ORDER BY updated_at DESC
            LIMIT 1
            """
        )
        with self.engine.begin() as conn:
            row = conn.execute(sql, {"file_hash": file_hash}).mappings().first()
            return dict(row) if row else None

    def get_by_doc_name(self, doc_name: str) -> dict[str, Any] | None:
        """根据文档名称查询已有文档（用于二次去重兜底）

        当 file_hash 去重未命中时，按文档名+活跃状态再查一次。
        只查询状态为 0（处理中）或 1（已入库）的文档。

        Args:
            doc_name: 文档名称

        Returns:
            匹配的文档记录字典，未找到则返回 None
        """
        sql = text(
            """
            SELECT *
            FROM knowledge_document
            WHERE doc_name = :doc_name
              AND status IN (0, 1)
            ORDER BY updated_at DESC
            LIMIT 1
            """
        )
        with self.engine.begin() as conn:
            row = conn.execute(sql, {"doc_name": doc_name}).mappings().first()
            return dict(row) if row else None

    def update_status(self, doc_id: str, status: int, remark: str | None = None) -> None:
        """更新文档状态

        支持同时更新备注信息（用于记录失败原因）。

        Args:
            doc_id: 文档 ID
            status: 目标状态值（0/1/2/3）
            remark: 备注信息（可选，如失败原因）
        """
        if remark is None:
            # 不更新 remark
            sql = text(
                "UPDATE knowledge_document SET status = :status, updated_at = NOW() WHERE doc_id = :doc_id"
            )
            params = {"doc_id": doc_id, "status": status}
        else:
            # 同时更新 status 和 remark
            sql = text(
                """
                UPDATE knowledge_document
                SET status = :status, remark = :remark, updated_at = NOW()
                WHERE doc_id = :doc_id
                """
            )
            params = {"doc_id": doc_id, "status": status, "remark": remark}

        with self.engine.begin() as conn:
            conn.execute(sql, params)

    def get_document(self, doc_id: str) -> dict[str, Any] | None:
        """按文档 ID 查询单条记录

        Args:
            doc_id: 文档 ID

        Returns:
            文档记录字典，不存在则返回 None
        """
        sql = text("SELECT * FROM knowledge_document WHERE doc_id = :doc_id")
        with self.engine.begin() as conn:
            row = conn.execute(sql, {"doc_id": doc_id}).mappings().first()
            return dict(row) if row else None

    def list_documents(self, status: int | None = None) -> list[dict[str, Any]]:
        """查询文档列表，按更新时间倒序

        Args:
            status: 可选的状态筛选条件，不传则返回全部

        Returns:
            文档记录字典列表
        """
        if status is not None:
            # 按状态筛选
            sql = text(
                "SELECT * FROM knowledge_document WHERE status = :status ORDER BY updated_at DESC"
            )
            with self.engine.begin() as conn:
                rows = conn.execute(sql, {"status": status}).mappings().all()
        else:
            # 查询全部
            sql = text("SELECT * FROM knowledge_document ORDER BY updated_at DESC")
            with self.engine.begin() as conn:
                rows = conn.execute(sql).mappings().all()
        return [dict(row) for row in rows]

    def delete_document(self, doc_id: str) -> None:
        """软删除文档（将状态设为 3）

        不实际删除数据，仅标记为已删除。

        Args:
            doc_id: 要删除的文档 ID
        """
        sql = text(
            "UPDATE knowledge_document SET status = 3, updated_at = NOW() WHERE doc_id = :doc_id"
        )
        with self.engine.begin() as conn:
            conn.execute(sql, {"doc_id": doc_id})

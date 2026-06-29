from __future__ import annotations

import re
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from app.core.config import Settings


class KnowledgeChunkRepository:
    """文档分片仓库

    操作 knowledge_chunk 表，提供文档分片的增删改查。
    分片状态定义：
        1 = 有效
        0 = 无效/已失效
    """

    def __init__(self, settings: Settings) -> None:
        """初始化仓库，创建数据库连接

        Args:
            settings: 全局配置对象，包含 database_url 连接串
        """
        self.engine: Engine = create_engine(settings.database_url, future=True)

    def create_chunk(
        self,
        chunk_id: str,
        doc_id: str,
        chunk_index: int,
        chunk_text: str,
        token_count: int | None = None,
        content_hash: str | None = None,
        chroma_doc_id: str | None = None,
        start_offset: int | None = None,
        end_offset: int | None = None,
    ) -> None:
        """插入单条分片记录（状态默认 1 = 有效）

        Args:
            chunk_id:      分片业务唯一标识
            doc_id:        所属文档 ID
            chunk_index:   文档内分片顺序（从 0 开始）
            chunk_text:    分片文本内容
            token_count:   分片 token 数（可选）
            content_hash:  分片文本 SHA256 哈希（可选，用于去重）
            chroma_doc_id: Chroma 向量库中对应的文档 ID（可选，入库后回填）
            start_offset:  在原文中的起始偏移（可选）
            end_offset:    在原文中的结束偏移（可选）
        """
        sql = text(
            """
            INSERT INTO knowledge_chunk
                (chunk_id, doc_id, chunk_index, chunk_text, token_count,
                 content_hash, chroma_doc_id, start_offset, end_offset,
                 status, created_at, updated_at)
            VALUES
                (:chunk_id, :doc_id, :chunk_index, :chunk_text, :token_count,
                 :content_hash, :chroma_doc_id, :start_offset, :end_offset,
                 1, NOW(), NOW())
            """
        )
        with self.engine.begin() as conn:
            conn.execute(
                sql,
                {
                    "chunk_id": chunk_id,
                    "doc_id": doc_id,
                    "chunk_index": chunk_index,
                    "chunk_text": chunk_text,
                    "token_count": token_count,
                    "content_hash": content_hash,
                    "chroma_doc_id": chroma_doc_id,
                    "start_offset": start_offset,
                    "end_offset": end_offset,
                },
            )

    def batch_create_chunks(self, chunks: list[dict[str, Any]]) -> None:
        """批量写入分片记录

        一次性写入多个分片，提高导入性能。
        每个字典必须包含 chunk_id、doc_id、chunk_index、chunk_text 等字段。

        Args:
            chunks: 分片记录字典列表，字典字段与 create_chunk 一致
        """
        sql = text(
            """
            INSERT INTO knowledge_chunk
                (chunk_id, doc_id, chunk_index, chunk_text, token_count,
                 content_hash, chroma_doc_id, start_offset, end_offset,
                 status, created_at, updated_at)
            VALUES
                (:chunk_id, :doc_id, :chunk_index, :chunk_text, :token_count,
                 :content_hash, :chroma_doc_id, :start_offset, :end_offset,
                 1, NOW(), NOW())
            """
        )
        with self.engine.begin() as conn:
            conn.execute(sql, chunks)

    def update_chroma_id(self, chunk_id: str, chroma_doc_id: str) -> None:
        """更新单个分片的 Chroma 文档 ID

        将 Chroma 向量库返回的文档 ID 回写到 MySQL 分片记录，
        建立 MySQL ↔ Chroma 的双向关联。

        Args:
            chunk_id:      分片 ID
            chroma_doc_id: Chroma 向量库中的文档 ID
        """
        sql = text(
            """
            UPDATE knowledge_chunk
            SET chroma_doc_id = :chroma_doc_id, updated_at = NOW()
            WHERE chunk_id = :chunk_id
            """
        )
        with self.engine.begin() as conn:
            conn.execute(sql, {"chunk_id": chunk_id, "chroma_doc_id": chroma_doc_id})

    def batch_update_chroma_ids(self, updates: list[dict[str, str]]) -> None:
        """批量更新分片的 Chroma 文档 ID

        Args:
            updates: 更新列表，每个元素为 {"chunk_id": ..., "chroma_doc_id": ...}
        """
        if not updates:
            # 空列表不执行，避免无效 SQL 调用
            return

        sql = text(
            """
            UPDATE knowledge_chunk
            SET chroma_doc_id = :chroma_doc_id, updated_at = NOW()
            WHERE chunk_id = :chunk_id
            """
        )
        with self.engine.begin() as conn:
            conn.execute(sql, updates)

    def get_chunks_by_doc_id(self, doc_id: str) -> list[dict[str, Any]]:
        """按文档 ID 查询所有有效分片

        只返回状态为 1（有效）的分片，按分片顺序排列。

        Args:
            doc_id: 文档 ID

        Returns:
            分片记录字典列表
        """
        sql = text(
            "SELECT * FROM knowledge_chunk WHERE doc_id = :doc_id AND status = 1 ORDER BY chunk_index ASC"
        )
        with self.engine.begin() as conn:
            rows = conn.execute(sql, {"doc_id": doc_id}).mappings().all()
            return [dict(row) for row in rows]

    def get_chunk_by_chroma_id(self, chroma_doc_id: str) -> dict[str, Any] | None:
        """根据 Chroma 文档 ID 反向查询分片记录

        建立从 Chroma 到 MySQL 的反向追溯能力。

        Args:
            chroma_doc_id: Chroma 向量库中的文档 ID

        Returns:
            分片记录字典，不存在则返回 None
        """
        sql = text(
            "SELECT * FROM knowledge_chunk WHERE chroma_doc_id = :chroma_doc_id"
        )
        with self.engine.begin() as conn:
            row = conn.execute(sql, {"chroma_doc_id": chroma_doc_id}).mappings().first()
            return dict(row) if row else None

    def search_keyword_candidates(
        self,
        query: str,
        terms: list[str],
        limit: int = 15,
    ) -> list[dict[str, Any]]:
        """按关键词召回候选分片

        基于 knowledge_chunk + knowledge_document 做简单关键词过滤，
        仅返回有效文档与有效分片，供 KeywordRetriever 做二次打分。

        Args:
            query: 原始查询文本
            terms: 预处理后的关键词列表
            limit: 返回候选数量上限

        Returns:
            候选分片记录列表
        """
        normalized_query = query.strip()
        normalized_terms = [term.strip() for term in terms if term.strip()]
        patterns: list[str] = []
        for value in [normalized_query, *normalized_terms]:
            pattern = value[:100]
            if pattern and pattern not in patterns:
                patterns.append(pattern)
        if not patterns:
            return []

        conditions: list[str] = []
        params: dict[str, Any] = {"limit": max(1, limit)}
        for idx, pattern in enumerate(patterns):
            escaped = self._escape_like(pattern)
            chunk_key = f"chunk_kw_{idx}"
            doc_key = f"doc_kw_{idx}"
            params[chunk_key] = f"%{escaped}%"
            params[doc_key] = f"%{escaped}%"
            conditions.append(
                f"(kc.chunk_text LIKE :{chunk_key} OR kd.doc_name LIKE :{doc_key})"
            )

        sql = text(
            f"""
            SELECT
                kc.chunk_id,
                kc.doc_id,
                kc.chunk_index,
                kc.chunk_text,
                kc.content_hash,
                kd.doc_name,
                kd.source_type,
                kd.source_path
            FROM knowledge_chunk kc
            INNER JOIN knowledge_document kd ON kd.doc_id = kc.doc_id
            WHERE kc.status = 1
              AND kd.status = 1
              AND ({' OR '.join(conditions)})
            ORDER BY kc.chunk_index ASC, kc.updated_at DESC
            LIMIT :limit
            """
        )
        with self.engine.begin() as conn:
            rows = conn.execute(sql, params).mappings().all()
            return [dict(row) for row in rows]

    def delete_chunks_by_doc_id(self, doc_id: str) -> None:
        """失效指定文档的所有分片（软删除）

        将状态设为 0（无效），不实际删除数据。
        通常用于回滚场景：文档导入失败时失效已写入的分片。

        Args:
            doc_id: 文档 ID
        """
        sql = text(
            "UPDATE knowledge_chunk SET status = 0, updated_at = NOW() WHERE doc_id = :doc_id"
        )
        with self.engine.begin() as conn:
            conn.execute(sql, {"doc_id": doc_id})

    @staticmethod
    def _escape_like(value: str) -> str:
        return re.sub(r"([%_\\])", r"\\\1", value)

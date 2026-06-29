from __future__ import annotations

import hashlib
import re
import uuid
from dataclasses import dataclass, field
from typing import Any

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.core.config import Settings
from app.rag.vector_retriever import VectorRetriever
from app.repositories.knowledge_chunk_repo import KnowledgeChunkRepository
from app.repositories.knowledge_document_repo import KnowledgeDocumentRepository


@dataclass
class DocumentInput:
    """第 1 步：统一的标准导入对象

    无论来源是什么（文本、文件、爬虫、课程同步…），
    最终都转为这个对象进入处理链路。

    字段说明：
        doc_name:    文档名称（如 "Java基础教程.txt"）
        source_type: 文档来源类型（manual / course / pdf / web / …）
        raw_text:    原始文本内容（未经清洗的原文）
        source_path: 来源路径或原始文件名（可选）
        version:     文档版本号，默认 "1.0"
        metadata:    附加元数据，如 {"author": "张三", "scene": "test"}
    """
    doc_name: str
    source_type: str
    raw_text: str
    source_path: str | None = None
    version: str = "1.0"
    metadata: dict[str, Any] = field(default_factory=dict)


class DocumentService:
    """文档导入服务

    三步处理架构：
        第 1 步：统一为 DocumentInput 标准对象
        第 2 步：_normalize_text() 清洗标准化
        第 3 步：_dedup_by_hash() 文档级去重
        最后：_process() 核心链路（MySQL 双写 + Chroma 向量化）
    """

    def __init__(self, settings: Settings) -> None:
        """初始化文档服务

        Args:
            settings: 全局配置对象
        """
        self.settings = settings
        # 向量检索器（Chroma 操作）
        self.retriever = VectorRetriever(settings)
        # 文档元数据仓库（knowledge_document 表）
        self.doc_repo = KnowledgeDocumentRepository(settings)
        # 文档分片仓库（knowledge_chunk 表）
        self.chunk_repo = KnowledgeChunkRepository(settings)

    # ═══════════════════════════════════════════════════
    # 外部入口
    # ═══════════════════════════════════════════════════

    def import_text(
        self,
        text: str,
        source: str = "manual",
        metadata: dict[str, Any] | None = None,
        chunk_size: int = 500,
        chunk_overlap: int = 50,
    ) -> dict[str, Any]:
        """兼容旧接口：直接传入文本字符串

        Args:
            text:         待导入的文本内容
            source:       文档来源类型，默认 "manual"
            metadata:     附加元数据（可选）
            chunk_size:   切分大小，默认 500 字符
            chunk_overlap:分片重叠大小，默认 50 字符

        Returns:
            导入结果字典，包含 doc_id、imported_chunks、status 等
        """
        # 将旧接口参数转换为统一的标准导入对象
        doc_input = DocumentInput(
            doc_name=f"{source}_{uuid.uuid4().hex[:8]}",
            source_type=source,
            raw_text=text,
            metadata=metadata or {},
        )
        return self._process(doc_input, chunk_size, chunk_overlap)

    def import_document(
        self,
        doc_input: DocumentInput,
        chunk_size: int = 500,
        chunk_overlap: int = 50,
    ) -> dict[str, Any]:
        """新入口：直接传入标准化的 DocumentInput 对象

        Args:
            doc_input:    标准化后的文档导入对象
            chunk_size:   切分大小，默认 500 字符
            chunk_overlap:分片重叠大小，默认 50 字符

        Returns:
            导入结果字典
        """
        return self._process(doc_input, chunk_size, chunk_overlap)

    # ═══════════════════════════════════════════════════
    # 第 2 步：文档标准化
    # ═══════════════════════════════════════════════════

    @staticmethod
    def _normalize_text(text: str) -> str:
        """清洗文本：去多余空白/换行、统一格式

        清理原则：
            - 统一换行符（\r\n → \n, \r → \n）
            - 去掉行尾多余空格和制表符
            - 连续空行压缩为最多一个空行（保留段落结构）
            - 多个连续空格缩为一个

        Args:
            text: 原始文本

        Returns:
            清洗后的文本
        """
        text = (text or "").strip()
        # 统一换行符为 \n
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        # 去掉行尾多余空白
        text = re.sub(r"[ \t]+\n", "\n", text)
        # 连续空行压缩（超过 2 个换行缩为 2 个，保留段落分隔）
        text = re.sub(r"\n{3,}", "\n\n", text)
        # 多个连续空格缩为一个
        text = re.sub(r"[ ]{2,}", " ", text)
        return text.strip()

    # ═══════════════════════════════════════════════════
    # 第 3 步：文档级去重
    # ═══════════════════════════════════════════════════

    def _dedup_by_hash(self, file_hash: str, doc_name: str | None = None) -> dict[str, Any] | None:
        """检查文档是否已存在（hash 去重 + doc_name 二次兜底）

        去重策略（按优先级）：
            1. file_hash 精准匹配（主要手段）
            2. doc_name 匹配（二次兜底，兜住历史数据 file_hash 为 NULL 的情况）

        Args:
            file_hash: 标准化后文本的 SHA256 哈希值
            doc_name:  文档名称（用于二次兜底查询）

        Returns:
            如果命中去重，返回已有文档信息字典；
            如果未命中，返回 None
        """
        # ── 策略 1：file_hash 精准匹配 ──
        existing = self.doc_repo.get_by_file_hash(file_hash)
        if existing:
            chunks = self.chunk_repo.get_chunks_by_doc_id(existing["doc_id"])
            return {
                "doc_id": existing["doc_id"],
                "doc_name": existing["doc_name"],
                "imported_chunks": len(chunks),
                "status": existing["status"],
                "duplicated": True,
                "message": "文档内容已存在，已跳过重复导入",
            }

        # ── 策略 2：doc_name 二次兜底 ──
        # 当 hash 未命中时，如果同名文档已存在（可能 file_hash 为 NULL），也视为重复
        if doc_name:
            existing_by_name = self.doc_repo.get_by_doc_name(doc_name)
            if existing_by_name:
                chunks = self.chunk_repo.get_chunks_by_doc_id(existing_by_name["doc_id"])
                return {
                    "doc_id": existing_by_name["doc_id"],
                    "doc_name": existing_by_name["doc_name"],
                    "imported_chunks": len(chunks),
                    "status": existing_by_name["status"],
                    "duplicated": True,
                    "message": f"同名文档「{doc_name}」已存在，已跳过重复导入",
                }

        return None

    # ═══════════════════════════════════════════════════
    # 核心处理链路
    # ═══════════════════════════════════════════════════

    def _process(
        self,
        doc_input: DocumentInput,
        chunk_size: int = 500,
        chunk_overlap: int = 50,
    ) -> dict[str, Any]:
        """文档导入核心处理链路

        流程：
            1. 标准化原始文本
            2. 用标准化后文本计算 hash 进行去重检查
            3. 写入 knowledge_document（元数据）
            4. 文本切片
            5. 批量写入 knowledge_chunk（分片）
            6. 写入 Chroma 向量库
            7. 回写 chroma_doc_id 到 knowledge_chunk
            8. 更新文档状态为成功（status=1）
            9. 异常时自动回滚：删 Chroma → 失效 chunk → 标记失败

        Args:
            doc_input:     标准化后的文档导入对象
            chunk_size:    切分大小
            chunk_overlap: 分片重叠大小

        Returns:
            导入结果字典
        """
        # ── 第 2 步：标准化 ──
        normalized_text = self._normalize_text(doc_input.raw_text)
        if not normalized_text:
            raise ValueError("导入文本不能为空")

        # ── 第 3 步：去重（用标准化后的文本计算 hash） ──
        file_hash = hashlib.sha256(normalized_text.encode("utf-8")).hexdigest()
        dup_result = self._dedup_by_hash(file_hash, doc_name=doc_input.doc_name)
        if dup_result:
            return dup_result

        # ── 正式入库 ──
        doc_id = uuid.uuid4().hex                            # 生成全局唯一文档 ID
        doc_name = doc_input.doc_name

        # 准备数据容器
        chunk_records: list[dict[str, Any]] = []             # MySQL chunk 记录
        langchain_docs: list[Document] = []                  # Chroma 文档对象
        chroma_ids: list[str] = []                           # Chroma 返回的 ID 列表

        # 先写入文档元数据，状态为 0（处理中）
        self.doc_repo.create_document(
            doc_id=doc_id,
            doc_name=doc_name,
            source_type=doc_input.source_type,
            source_path=doc_input.source_path,
            version=doc_input.version,
            file_hash=file_hash,
        )

        try:
            # ── 文本切片 ──
            splitter = RecursiveCharacterTextSplitter(
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
            )
            chunks = splitter.split_text(normalized_text)
            if not chunks:
                raise ValueError("文本切片结果为空，无法导入")

            # 构建切片基础元数据（会被合并到每个 chunk 的 metadata 中）
            base_meta = {
                "source": doc_input.source_type,
                "doc_id": doc_id,
                **doc_input.metadata,
            }

            # ── 逐片生成记录 ──
            for i, chunk_text in enumerate(chunks):
                chunk_id = f"{doc_id}_{i:04d}"                # 分片唯一 ID
                content_hash = hashlib.sha256(chunk_text.encode("utf-8")).hexdigest()

                # MySQL 分片记录
                chunk_records.append({
                    "chunk_id": chunk_id,
                    "doc_id": doc_id,
                    "chunk_index": i,
                    "chunk_text": chunk_text,
                    "token_count": None,                      # token 数暂不计算
                    "content_hash": content_hash,
                    "chroma_doc_id": None,                    # 暂未写入 Chroma
                    "start_offset": None,
                    "end_offset": None,
                })
                # Chroma 文档对象（LangChain 格式）
                langchain_docs.append(
                    Document(
                        page_content=chunk_text,
                        metadata={**base_meta, "chunk_index": i, "chunk_id": chunk_id},
                    )
                )

            # ── 批量写入 MySQL knowledge_chunk ──
            self.chunk_repo.batch_create_chunks(chunk_records)

            # ── 批量写入 Chroma 向量库 ──
            chroma_ids = self.retriever.add_documents(langchain_docs)
            if len(chroma_ids) != len(chunk_records):
                raise RuntimeError("Chroma 返回的文档 ID 数量与分片数量不一致")

            # ── 回写 chroma_doc_id 到 MySQL ──
            updates = [
                {"chunk_id": cr["chunk_id"], "chroma_doc_id": cid}
                for cr, cid in zip(chunk_records, chroma_ids)
            ]
            self.chunk_repo.batch_update_chroma_ids(updates)

            # ── 更新文档状态为"已入库" ──
            self.doc_repo.update_status(doc_id=doc_id, status=1, remark=None)

            return {
                "doc_id": doc_id,
                "doc_name": doc_name,
                "imported_chunks": len(chunks),
                "status": 1,                                     # 1=成功
                "duplicated": False,
                "message": "文档导入成功",
            }

        except Exception as exc:
            """异常回滚策略

            如果导入过程中出现任何异常，依次执行：
                1. 从 Chroma 删除已写入的向量文档
                2. 失效 MySQL 中已写入的分片记录（status=0）
                3. 更新文档状态为失败（status=2）+ 记录错误信息
            """
            error_msg = f"导入失败: {str(exc)[:450]}"

            # 回滚 1：删除 Chroma 中已写入的文档
            if chroma_ids:
                try:
                    self.retriever.delete_documents(chroma_ids)
                except Exception:
                    pass
            # 回滚 2：失效 MySQL chunk 记录
            try:
                self.chunk_repo.delete_chunks_by_doc_id(doc_id)
            except Exception:
                pass
            # 回滚 3：标记文档导入失败
            try:
                self.doc_repo.update_status(doc_id=doc_id, status=2, remark=error_msg)
            except Exception:
                pass

            # 继续向上抛出原始异常
            raise

from __future__ import annotations

import os
from typing import Any

import chromadb
from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings

from app.core.config import Settings
from app.providers.embedding import build_embedding_model

# Chroma 集合名称
_COLLECTION = "tj_aigc_docs"
# 项目根目录（向上三层，从 app/rag 到项目根）
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# Chroma 持久化目录（项目根目录下的 chroma_db/）
_PERSIST_DIR = os.path.join(_PROJECT_ROOT, "chroma_db")


class VectorRetriever:
    """向量检索器

    基于 Chroma 向量数据库的封装，提供文档的向量化存储和语义检索能力。
    使用 LangChain 的 Chroma 封装，支持添加文档、相似度检索、按 ID 删除等操作。

    使用方式：
        retriever = VectorRetriever(settings)
        retriever.add_documents(docs)       # 添加文档到向量库
        results = retriever.retrieve(query) # 语义检索
    """

    def __init__(self, settings: Settings) -> None:
        """初始化向量检索器

        采用懒加载方式，embedding 模型和 Chroma 存储对象在使用时才会初始化。

        Args:
            settings: 全局配置对象，包含 embedding 模型配置
        """
        self.settings = settings
        # embedding 模型实例（懒加载）
        self._embedding: Embeddings | None = None
        # Chroma 存储实例（懒加载）
        self._store: Chroma | None = None

    @property
    def embedding(self) -> Embeddings:
        """获取 embedding 模型实例（懒加载）

        首次访问时根据配置构建模型，支持千问 / DeepSeek 等兼容 OpenAI 接口的模型。

        Returns:
            Embeddings 模型实例
        """
        if self._embedding is None:
            self._embedding = build_embedding_model(self.settings)
        return self._embedding

    @property
    def store(self) -> Chroma:
        """获取 Chroma 存储实例（懒加载）

        首次访问时创建持久化客户端并连接到指定集合。
        向量数据将持久化到项目根目录的 chroma_db/ 文件夹。

        Returns:
            Chroma 存储实例
        """
        if self._store is None:
            # 创建 Chroma 持久化客户端
            client = chromadb.PersistentClient(path=_PERSIST_DIR)
            # 通过 LangChain 封装连接到集合
            self._store = Chroma(
                client=client,
                collection_name=_COLLECTION,
                embedding_function=self.embedding,
                persist_directory=_PERSIST_DIR,
            )
        return self._store

    def add_documents(self, documents: list[Document]) -> list[str]:
        """向 Chroma 向量库添加文档

        将文档列表向量化后存入 Chroma，返回每个文档对应的 Chroma ID。

        Args:
            documents: LangChain Document 对象列表（包含 page_content 和 metadata）

        Returns:
            Chroma 分配的文档 ID 列表，与输入 documents 一一对应
        """
        return self.store.add_documents(documents)

    def delete_documents(self, document_ids: list[str]) -> None:
        """从 Chroma 向量库删除指定文档

        通常用于异常回滚场景：文档导入失败时清理已写入的向量数据。

        Args:
            document_ids: 要删除的 Chroma 文档 ID 列表
        """
        if not document_ids:
            # 空列表不执行
            return
        self.store.delete(ids=document_ids)

    def retrieve(self, query: str, top_k: int = 5) -> list[dict[str, Any]]:
        """语义检索：根据查询文本召回最相似的分片

        使用相似度搜索（带相关性分数），返回按相似度降序排列的结果。

        Args:
            query:  用户查询文本
            top_k:  返回结果数量，默认 5 条

        Returns:
            检索结果列表，每个元素包含：
                - content:  分片文本内容
                - metadata: 分片元数据（来源、文档 ID、chunk ID 等）
                - score:    相似度分数（0~1，越大越相关）
        """
        # 执行相似度搜索，返回 (文档, 分数) 的列表
        docs = self.store.similarity_search_with_relevance_scores(query, k=top_k)
        return [
            {
                "content": doc.page_content,
                "metadata": doc.metadata,
                "score": score,
            }
            for doc, score in docs
        ]

    def delete_collection(self) -> None:
        """清空整个 Chroma 集合

        删除当前集合中的所有向量数据。
        常用于测试环境重置或数据全量重建场景。
        """
        try:
            client = chromadb.PersistentClient(path=_PERSIST_DIR)
            client.delete_collection(_COLLECTION)
        except Exception:
            # 集合不存在时忽略异常
            pass
        # 清除缓存，下次访问时会重新创建
        self._store = None

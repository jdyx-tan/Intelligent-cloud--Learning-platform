from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


# ─── 会话相关 ───

class ChatDTO(BaseModel):
    question: str
    sessionId: str


class SessionExample(BaseModel):
    title: str
    describe: str


class SessionVO(BaseModel):
    sessionId: str
    title: str
    describe: str
    examples: list[SessionExample]


class ChatSessionVO(BaseModel):
    sessionId: str
    title: str | None = None
    summary: str | None = None
    status: int | None = None
    messageCount: int | None = None
    lastMessageAt: datetime | None = None
    updateTime: datetime | None = None


class MessageVO(BaseModel):
    type: Literal["USER", "ASSISTANT"]
    content: str
    params: dict[str, Any] | None = None


class TemplateVO(BaseModel):
    associationalWord: str = Field(default="用户输入关键词：$input|生成规则：生成3个，每个问题含【$input】不超过20字|输出要求：纯文本，问题间用|分隔")
    helpedWrite: str = Field(default="基于用户提供的主题/关键词，智能生成完整的文案内容（如文章、邮件、报告等），帮助用户快速搭建内容框架\n用户输入：\n$input")
    continuedWrite: str = Field(default="在用户已有文本基础上，自动延续写作思路生成后续内容，保持上下文逻辑连贯性\n用户输入：\n$input")
    polish: str = Field(default="对现有文本进行语言优化，包括调整句式结构、替换精准词汇、统一行文风格等\n用户输入：\n$input")
    streamline: str = Field(default="通过语义分析智能提炼核心信息，删除几余表达，将长文本压缩为简洁版本\n用户输入：\n$input")


class ChatMessageVO(BaseModel):
    messageId: str
    sessionId: str
    role: str
    content: str
    messageOrder: int | None = None
    tokenCount: int | None = None
    inputTokens: int | None = None
    outputTokens: int | None = None
    modelName: str | None = None
    createdAt: datetime | None = None


# ─── 知识库相关 ───

class KnowledgeDocumentVO(BaseModel):
    docId: str
    docName: str
    sourceType: str
    sourcePath: str | None = None
    version: str
    status: int
    fileHash: str | None = None
    remark: str | None = None
    createdAt: datetime | None = None
    updatedAt: datetime | None = None


class KnowledgeChunkVO(BaseModel):
    chunkId: str
    docId: str
    chunkIndex: int
    chunkText: str
    tokenCount: int | None = None
    chromaDocId: str | None = None


# ─── RAG 日志相关 ───

class RagQueryLogVO(BaseModel):
    queryLogId: str
    sessionId: str
    messageId: str
    userQuery: str
    rewrittenQuery: str | None = None
    retrievedChunkIds: list[str] | None = None
    retrievedScores: list[float] | None = None
    answerText: str | None = None
    retrievalStatus: int
    answerStatus: int
    latencyMs: int
    errorMsg: str | None = None
    createdAt: datetime | None = None

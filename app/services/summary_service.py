from __future__ import annotations

from langchain_core.messages import HumanMessage, SystemMessage

from app.core.config import Settings
from app.domain.models import MessageVO
from app.providers.llm import build_text_model
from app.repositories.chat_session_repo import ChatSessionRepository
from app.repositories.summary_snapshot_repo import SummarySnapshotRepository

_SUMMARY_PROMPT = (
    "请用简洁的语言总结以上对话的核心内容，保留关键信息（用户意图、关键问题、重要结论），"
    "控制在200字以内，用中文输出。"
)


class SummaryService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.model = build_text_model(settings)
        self.repo = SummarySnapshotRepository(settings)
        self.session_repo = ChatSessionRepository(settings)

    def generate_summary(self, messages: list[MessageVO]) -> str:
        """调用 LLM 生成一段对话摘要。"""
        msgs: list = [SystemMessage(content=_SUMMARY_PROMPT)]
        for msg in messages:
            role = "用户" if msg.type == "USER" else "AI"
            msgs.append(HumanMessage(content=f"{role}：{msg.content}"))
        response = self.model.invoke(msgs)
        content = response.content
        if isinstance(content, list):
            return "".join(str(item) for item in content)
        return str(content)

    def get_latest_summary(self, session_id: str) -> str | None:
        """获取最近一份摘要文本。"""
        snapshot = self.repo.get_latest_snapshot(session_id)
        return snapshot["summary_text"] if snapshot else None

    def get_summary_message_count(self, session_id: str) -> int:
        """获取最近摘要已覆盖的消息条数，没有摘要则返回0。"""
        snapshot = self.repo.get_latest_snapshot(session_id)
        return snapshot["message_count"] if snapshot else 0

    def try_generate_summary(
        self,
        session_id: str,
        all_messages: list[MessageVO],
        threshold: int = 6,
    ) -> str | None:
        """如果总消息数超过阈值则生成摘要并持久化，否则返回 None。"""
        total = len(all_messages)
        covered = self.get_summary_message_count(session_id)

        # 新增消息不够多，不触发摘要
        if total - covered < threshold:
            return None

        summary = self.generate_summary(all_messages)
        # 计算下一个版本号
        latest = self.repo.get_latest_snapshot(session_id)
        version = (latest["version"] + 1) if latest else 1

        self.repo.save_snapshot(
            session_id=session_id,
            summary_text=summary,
            message_count=total,
            version=version,
        )
        self.session_repo.update_session_summary(session_id=session_id, summary=summary)
        return summary

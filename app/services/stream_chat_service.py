from __future__ import annotations

import json
import time
from collections.abc import Iterator

from app.core.config import Settings
from app.domain.events import ChatEventType, ChatEventVO
from app.domain.models import MessageVO
from app.memory.redis_history import RedisHistoryStore
from app.repositories.chat_message_repo import ChatMessageRepository
from app.repositories.chat_session_repo import ChatSessionRepository
from app.repositories.rag_query_log_repo import RagQueryLogRepository
from app.services.agent_service import AgentService, AgentTrace
from app.services.summary_service import SummaryService

_SUMMARY_THRESHOLD = 6  # 新增多少条消息后触发摘要生成


class StreamChatService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.agent = AgentService(settings)
        self.message_repo = ChatMessageRepository(settings)
        self.session_repo = ChatSessionRepository(settings)
        self.rag_log_repo = RagQueryLogRepository(settings)
        self.redis = RedisHistoryStore(settings)
        self.summary_service = SummaryService(settings)

    def stop(self, session_id: str) -> None:
        self.redis.stop(session_id)

    def clear_stop(self, session_id: str) -> None:
        self.redis.clear_stop(session_id)

    def is_stopped(self, session_id: str) -> bool:
        return self.redis.is_stopped(session_id)

    def stream_chat(self, user_id: int, question: str, session_id: str) -> Iterator[str]:
        self.clear_stop(session_id)
        trace = AgentTrace()
        start_time = time.perf_counter()

        # 先查历史上下文（不包含当前问题）
        history_rows = self.message_repo.list_messages(
            session_id=session_id, user_id=user_id
        )
        history = [
            MessageVO(type=row["role"], content=row["content"])
            for row in history_rows
        ]

        # 查询最新摘要
        summary = self.summary_service.get_latest_summary(session_id)

        # 保存用户消息
        user_message_id = self.message_repo.save_message(
            session_id=session_id,
            user_id=user_id,
            role="USER",
            content=question,
        )

        # 顺手更新 session 标题
        self.session_repo.touch_session_title(
            session_id=session_id,
            user_id=user_id,
            title=question,
        )

        chunks: list[str] = []
        answer_status = 1
        error_msg: str | None = None

        try:
            for chunk in self.agent.stream_chat(question, history=history, summary=summary, trace=trace):
                if self.is_stopped(session_id):
                    answer_status = 0
                    error_msg = "生成已被用户停止"
                    break
                if not chunk:
                    continue
                chunks.append(chunk)
                yield self._to_sse(
                    ChatEventVO(
                        eventData=chunk,
                        eventType=ChatEventType.DATA,
                    )
                )
        except Exception as exc:
            answer_status = 0
            error_msg = str(exc)
            raise
        finally:
            final_answer = "".join(chunks)
            latency_ms = int((time.perf_counter() - start_time) * 1000)

            if final_answer:
                self.message_repo.save_message(
                    session_id=session_id,
                    user_id=user_id,
                    role="ASSISTANT",
                    content=final_answer,
                )

                # 本轮完整消息后触发摘要生成
                self.summary_service.try_generate_summary(
                    session_id=session_id,
                    all_messages=history
                    + [
                        MessageVO(type="USER", content=question),
                        MessageVO(type="ASSISTANT", content=final_answer),
                    ],
                    threshold=_SUMMARY_THRESHOLD,
                )

            self.rag_log_repo.save_log(
                session_id=session_id,
                message_id=user_message_id,
                user_query=question,
                rewritten_query=None,
                retrieved_chunk_ids=trace.retrieved_chunk_ids or None,
                retrieved_scores=trace.retrieved_scores or None,
                top_k=3,
                final_top_n=len(trace.retrieved_chunk_ids) if trace.retrieved_chunk_ids else 0,
                prompt_snapshot=trace.prompt_snapshot,
                answer_text=final_answer or None,
                retrieval_status=1,
                answer_status=answer_status,
                latency_ms=latency_ms,
                error_msg=error_msg,
            )

            self.clear_stop(session_id)

        yield self._to_sse(ChatEventVO(eventType=ChatEventType.STOP))

    @staticmethod
    def _to_sse(event: ChatEventVO) -> str:
        return f"data:{json.dumps(event.model_dump(), ensure_ascii=False)}\n\n"

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from app.core.config import Settings
from app.domain.models import MessageVO
from app.providers.llm import build_text_model
from app.rag.hybrid_retriever import HybridRetriever
from app.services.prompt_service import PromptService
from app.tools.course_tools import (
    query_course_info,
    recommend_best_courses,
    recommend_courses,
    recommend_new_courses,
)
from app.tools.order_tools import pre_place_order

_RECENT_LIMIT = 4


@dataclass
class AgentTrace:
    retrieved_chunk_ids: list[str] = field(default_factory=list)
    retrieved_scores: list[float] = field(default_factory=list)
    tool_names: list[str] = field(default_factory=list)
    prompt_snapshot: str | None = None
    context: str | None = None


class AgentService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.prompt_service = PromptService(settings)
        self.retriever = HybridRetriever(settings)
        self.tools = [
            query_course_info,
            recommend_courses,
            recommend_best_courses,
            recommend_new_courses,
            pre_place_order,
        ]
        self._model = build_text_model(settings)
        self._tool_model = self._model.bind_tools(self.tools)

    def build_messages(
        self,
        question: str,
        history: list[MessageVO] | None = None,
        summary: str | None = None,
        context: str | None = None,
    ) -> list:
        prompt = self.prompt_service.get_text_prompt()
        messages: list = [SystemMessage(content=prompt)]

        if context:
            messages.append(SystemMessage(content=f"以下是知识库检索到的相关资料：\n{context}"))

        if summary:
            messages.append(SystemMessage(content=f"以下是对话历史摘要：\n{summary}"))
            if history:
                recent = history[-_RECENT_LIMIT:]
                for msg in recent:
                    if msg.type == "USER":
                        messages.append(HumanMessage(content=msg.content))
                    else:
                        messages.append(AIMessage(content=msg.content))
        elif history:
            for msg in history:
                if msg.type == "USER":
                    messages.append(HumanMessage(content=msg.content))
                else:
                    messages.append(AIMessage(content=msg.content))

        messages.append(HumanMessage(content=question))
        return messages

    def chat(
        self,
        question: str,
        history: list[MessageVO] | None = None,
        summary: str | None = None,
        trace: AgentTrace | None = None,
    ) -> str:
        # 1. RAG 检索
        context = self.retrieve_context(question, trace=trace)

        # 2. 构建消息
        messages = self.build_messages(question, history=history, summary=summary, context=context)
        if trace is not None:
            trace.context = context
            trace.prompt_snapshot = self._messages_to_text(messages)

        # 3. 调用模型（带 tool binding）
        response = self._tool_model.invoke(messages)

        # 4. 如果模型决定调用工具
        if response.tool_calls:
            messages.append(response)
            self._append_tool_results(messages, response.tool_calls, trace=trace)
            if trace is not None:
                trace.prompt_snapshot = self._messages_to_text(messages)
            # 将工具结果重新发给模型生成最终回答
            final_response = self._model.invoke(messages)
            return self._extract_content(final_response.content)

        return self._extract_content(response.content)

    def stream_chat(
        self,
        question: str,
        history: list[MessageVO] | None = None,
        summary: str | None = None,
        trace: AgentTrace | None = None,
    ) -> Iterator[str]:
        context = self.retrieve_context(question, trace=trace)
        messages = self.build_messages(question, history=history, summary=summary, context=context)
        if trace is not None:
            trace.context = context
            trace.prompt_snapshot = self._messages_to_text(messages)

        first_response = None
        saw_tool_calls = False

        for chunk in self._tool_model.stream(messages):
            first_response = chunk if first_response is None else first_response + chunk
            if getattr(chunk, "tool_call_chunks", None) or getattr(chunk, "tool_calls", None):
                saw_tool_calls = True
            text = self._extract_content(chunk.content)
            if text and not saw_tool_calls:
                yield text

        if first_response and getattr(first_response, "tool_calls", None):
            messages.append(
                AIMessage(
                    content=self._extract_content(first_response.content),
                    tool_calls=first_response.tool_calls,
                )
            )
            self._append_tool_results(messages, first_response.tool_calls, trace=trace)
            if trace is not None:
                trace.prompt_snapshot = self._messages_to_text(messages)
            for chunk in self._model.stream(messages):
                text = self._extract_content(chunk.content)
                if text:
                    yield text

    def retrieve_context(self, question: str, top_k: int = 3, trace: AgentTrace | None = None) -> str:
        results = self.retriever.retrieve(question, top_k=top_k)
        if trace is not None:
            trace.retrieved_chunk_ids = [
                r.metadata.get("chunk_id")
                for r in results
                if hasattr(r, "metadata") and r.metadata.get("chunk_id")
            ]
            trace.retrieved_scores = [float(r.score) for r in results]
        if not results:
            return ""
        context_parts = []
        for r in results:
            source = r.metadata.get("source", "知识库") if hasattr(r, "metadata") else "知识库"
            context_parts.append(f"[来自 {source}]\n{r.content}")
        return "\n\n".join(context_parts)

    def _append_tool_results(self, messages: list, tool_calls: list[dict], trace: AgentTrace | None = None) -> None:
        for tool_call in tool_calls:
            tool_name = tool_call["name"]
            tool_args = tool_call["args"]
            if trace is not None:
                trace.tool_names.append(tool_name)
            for t in self.tools:
                if t.name == tool_name:
                    try:
                        tool_result = t.invoke(tool_args)
                    except Exception as exc:
                        tool_result = (
                            f"工具「{tool_name}」调用失败：{exc}。"
                            "请不要中断回答，优先基于已有知识库内容继续作答，"
                            "并明确说明当前实时服务暂不可用或信息可能不完整。"
                        )
                    messages.append(HumanMessage(content=f"工具「{tool_name}」返回结果：\n{tool_result}"))
                    break

    @staticmethod
    def _extract_content(content: str | list | None) -> str:
        if content is None:
            return ""
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            return "".join(str(item) for item in content)
        return str(content)

    @staticmethod
    def _messages_to_text(messages: list) -> str:
        parts: list[str] = []
        for msg in messages:
            role = getattr(msg, "type", msg.__class__.__name__)
            parts.append(f"[{role}] {getattr(msg, 'content', '')}")
        return "\n".join(parts)

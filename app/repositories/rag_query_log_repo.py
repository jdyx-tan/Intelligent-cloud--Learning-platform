from __future__ import annotations

import json
import uuid
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from app.core.config import Settings


class RagQueryLogRepository:
    def __init__(self, settings: Settings) -> None:
        self.engine: Engine = create_engine(settings.database_url, future=True)

    def save_log(
        self,
        session_id: str,
        message_id: str,
        user_query: str,
        rewritten_query: str | None = None,
        retrieved_chunk_ids: list[str] | None = None,
        retrieved_scores: list[float] | None = None,
        top_k: int | None = None,
        final_top_n: int | None = None,
        prompt_snapshot: str | None = None,
        answer_text: str | None = None,
        retrieval_status: int = 1,
        answer_status: int = 1,
        latency_ms: int = 0,
        error_msg: str | None = None,
    ) -> str:
        query_log_id = uuid.uuid4().hex
        sql = text(
            """
            INSERT INTO rag_query_log
                (query_log_id, session_id, message_id, user_query, rewritten_query,
                 retrieved_chunk_ids, retrieved_scores, top_k, final_top_n,
                 prompt_snapshot, answer_text, retrieval_status, answer_status,
                 latency_ms, error_msg, created_at)
            VALUES
                (:query_log_id, :session_id, :message_id, :user_query, :rewritten_query,
                 :retrieved_chunk_ids, :retrieved_scores, :top_k, :final_top_n,
                 :prompt_snapshot, :answer_text, :retrieval_status, :answer_status,
                 :latency_ms, :error_msg, NOW())
            """
        )
        with self.engine.begin() as conn:
            conn.execute(
                sql,
                {
                    "query_log_id": query_log_id,
                    "session_id": session_id,
                    "message_id": message_id,
                    "user_query": user_query,
                    "rewritten_query": rewritten_query,
                    "retrieved_chunk_ids": json.dumps(retrieved_chunk_ids, ensure_ascii=False) if retrieved_chunk_ids else None,
                    "retrieved_scores": json.dumps(retrieved_scores) if retrieved_scores else None,
                    "top_k": top_k,
                    "final_top_n": final_top_n,
                    "prompt_snapshot": prompt_snapshot,
                    "answer_text": answer_text,
                    "retrieval_status": retrieval_status,
                    "answer_status": answer_status,
                    "latency_ms": latency_ms,
                    "error_msg": error_msg,
                },
            )
        return query_log_id

    def list_logs_by_session(
        self, session_id: str, limit: int = 50
    ) -> list[dict[str, Any]]:
        sql = text(
            "SELECT * FROM rag_query_log WHERE session_id = :session_id ORDER BY created_at DESC LIMIT :limit"
        )
        with self.engine.begin() as conn:
            rows = conn.execute(sql, {"session_id": session_id, "limit": limit}).mappings().all()
            return [dict(row) for row in rows]

    def get_log(self, query_log_id: str) -> dict[str, Any] | None:
        sql = text("SELECT * FROM rag_query_log WHERE query_log_id = :query_log_id")
        with self.engine.begin() as conn:
            row = conn.execute(sql, {"query_log_id": query_log_id}).mappings().first()
            return dict(row) if row else None

    def list_failed_logs(self, limit: int = 20) -> list[dict[str, Any]]:
        sql = text(
            "SELECT * FROM rag_query_log WHERE retrieval_status = 0 OR answer_status = 0 ORDER BY created_at DESC LIMIT :limit"
        )
        with self.engine.begin() as conn:
            rows = conn.execute(sql, {"limit": limit}).mappings().all()
            return [dict(row) for row in rows]

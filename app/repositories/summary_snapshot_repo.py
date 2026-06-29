from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from app.core.config import Settings


class SummarySnapshotRepository:
    def __init__(self, settings: Settings) -> None:
        self.engine: Engine = create_engine(settings.database_url, future=True)

    def save_snapshot(
        self,
        session_id: str,
        summary_text: str,
        message_count: int,
        version: int = 1,
        start_message_id: str | None = None,
        end_message_id: str | None = None,
    ) -> str:
        snapshot_id = uuid.uuid4().hex
        sql = text(
            """
            INSERT INTO session_summary_snapshot
                (snapshot_id, session_id, summary_text, message_count, version,
                 start_message_id, end_message_id, status, created_at)
            VALUES
                (:snapshot_id, :session_id, :summary_text, :message_count, :version,
                 :start_message_id, :end_message_id, 1, NOW())
            """
        )
        with self.engine.begin() as conn:
            conn.execute(
                sql,
                {
                    "snapshot_id": snapshot_id,
                    "session_id": session_id,
                    "summary_text": summary_text,
                    "message_count": message_count,
                    "version": version,
                    "start_message_id": start_message_id,
                    "end_message_id": end_message_id,
                },
            )
        return snapshot_id

    def get_latest_snapshot(self, session_id: str) -> dict[str, Any] | None:
        sql = text(
            """
            SELECT snapshot_id, summary_text, message_count, version,
                   start_message_id, end_message_id, status, created_at
            FROM session_summary_snapshot
            WHERE session_id = :session_id AND status = 1
            ORDER BY version DESC
            LIMIT 1
            """
        )
        with self.engine.begin() as conn:
            row = conn.execute(sql, {"session_id": session_id}).mappings().first()
            return dict(row) if row else None

    def list_snapshots(self, session_id: str) -> list[dict[str, Any]]:
        sql = text(
            """
            SELECT snapshot_id, summary_text, message_count, version,
                   start_message_id, end_message_id, status, created_at
            FROM session_summary_snapshot
            WHERE session_id = :session_id AND status = 1
            ORDER BY version ASC
            """
        )
        with self.engine.begin() as conn:
            rows = conn.execute(sql, {"session_id": session_id}).mappings().all()
            return [dict(row) for row in rows]

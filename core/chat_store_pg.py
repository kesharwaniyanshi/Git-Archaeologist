"""PostgreSQL-backed chat session and message storage."""

from __future__ import annotations

import json
import uuid
from typing import Dict, List, Optional

from sqlalchemy import text

from .db import get_engine


class PostgresChatStore:
    """Persistent chat storage in PostgreSQL."""

    def __init__(self):
        self.engine = get_engine()
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        with self.engine.begin() as connection:
            connection.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS chat_sessions (
                        id TEXT PRIMARY KEY,
                        repository_id BIGINT REFERENCES repositories(id) ON DELETE SET NULL,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                        updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
                    )
                    """
                )
            )
            connection.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS chat_messages (
                        id BIGSERIAL PRIMARY KEY,
                        chat_session_id TEXT NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
                        role TEXT NOT NULL,
                        content TEXT NOT NULL,
                        message_metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT now()
                    )
                    """
                )
            )
            connection.execute(
                text(
                    """
                    CREATE INDEX IF NOT EXISTS idx_chat_messages_session_time
                    ON chat_messages (chat_session_id, created_at)
                    """
                )
            )

    def _get_repository_id(self, repo_path: Optional[str]) -> Optional[int]:
        if not repo_path:
            return None

        with self.engine.begin() as connection:
            row = connection.execute(
                text("SELECT id FROM repositories WHERE repo_path = :repo_path"),
                {"repo_path": repo_path},
            ).one_or_none()

        if not row:
            return None
        return int(row[0])

    def create_session(self, repo_path: Optional[str] = None) -> str:
        session_id = str(uuid.uuid4())
        repository_id = self._get_repository_id(repo_path)

        with self.engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO chat_sessions (id, repository_id, created_at, updated_at)
                    VALUES (:id, :repository_id, now(), now())
                    """
                ),
                {"id": session_id, "repository_id": repository_id},
            )

        return session_id

    def session_exists(self, session_id: str) -> bool:
        with self.engine.begin() as connection:
            row = connection.execute(
                text("SELECT 1 FROM chat_sessions WHERE id = :id"),
                {"id": session_id},
            ).one_or_none()
        return row is not None

    def append_message(
        self,
        session_id: str,
        role: str,
        content: str,
        message_metadata: Optional[Dict] = None,
    ) -> None:
        payload = message_metadata or {}

        with self.engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO chat_messages (chat_session_id, role, content, message_metadata, created_at)
                    VALUES (:chat_session_id, :role, :content, CAST(:message_metadata AS jsonb), now())
                    """
                ),
                {
                    "chat_session_id": session_id,
                    "role": role,
                    "content": content,
                    "message_metadata": json.dumps(payload),
                },
            )
            connection.execute(
                text("UPDATE chat_sessions SET updated_at = now() WHERE id = :id"),
                {"id": session_id},
            )

    def get_messages(self, session_id: str, limit: int = 200) -> List[Dict]:
        with self.engine.begin() as connection:
            rows = connection.execute(
                text(
                    """
                    SELECT role, content, message_metadata, created_at
                    FROM chat_messages
                    WHERE chat_session_id = :chat_session_id
                    ORDER BY created_at ASC
                    LIMIT :limit
                    """
                ),
                {
                    "chat_session_id": session_id,
                    "limit": limit,
                },
            ).fetchall()

        messages: List[Dict] = []
        for row in rows:
            metadata = row[2]
            if isinstance(metadata, str):
                metadata = json.loads(metadata)
            messages.append(
                {
                    "role": row[0],
                    "content": row[1],
                    "metadata": metadata,
                    "created_at": row[3].isoformat() if row[3] is not None else None,
                }
            )
        return messages

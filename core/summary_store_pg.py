"""PostgreSQL-backed commit summary storage."""

from __future__ import annotations

from typing import Dict, List, Optional

from sqlalchemy import text

from .db import get_engine


class PostgresSummaryStore:
    """Persistent storage for commit summaries to avoid repeated LLM calls."""

    def __init__(self):
        self.engine = get_engine()
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        with self.engine.begin() as connection:
            connection.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS commit_summaries (
                        commit_hash TEXT PRIMARY KEY,
                        message TEXT NOT NULL,
                        summary TEXT NOT NULL,
                        status TEXT NOT NULL,
                        error TEXT,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                        updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
                    )
                    """
                )
            )
            connection.execute(
                text(
                    """
                    CREATE INDEX IF NOT EXISTS idx_commit_summaries_updated_at
                    ON commit_summaries (updated_at DESC)
                    """
                )
            )

    def get_summary(self, commit_hash: str) -> Optional[Dict]:
        with self.engine.begin() as connection:
            row = connection.execute(
                text(
                    """
                    SELECT commit_hash, message, summary, status, error
                    FROM commit_summaries
                    WHERE commit_hash = :commit_hash
                    """
                ),
                {"commit_hash": commit_hash},
            ).one_or_none()

        if not row:
            return None

        return {
            "hash": row[0],
            "message": row[1],
            "summary": row[2],
            "status": row[3],
            "error": row[4],
        }

    def upsert_summary(self, summary: Dict) -> None:
        commit_hash = summary.get("hash")
        if not commit_hash:
            return

        with self.engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO commit_summaries (commit_hash, message, summary, status, error, created_at, updated_at)
                    VALUES (:commit_hash, :message, :summary, :status, :error, now(), now())
                    ON CONFLICT (commit_hash)
                    DO UPDATE SET
                        message = EXCLUDED.message,
                        summary = EXCLUDED.summary,
                        status = EXCLUDED.status,
                        error = EXCLUDED.error,
                        updated_at = now()
                    """
                ),
                {
                    "commit_hash": commit_hash,
                    "message": summary.get("message", ""),
                    "summary": summary.get("summary", ""),
                    "status": summary.get("status", "success"),
                    "error": summary.get("error"),
                },
            )

    def get_summaries_for_hashes(self, commit_hashes: List[str]) -> Dict[str, Dict]:
        if not commit_hashes:
            return {}

        with self.engine.begin() as connection:
            rows = connection.execute(
                text(
                    """
                    SELECT commit_hash, message, summary, status, error
                    FROM commit_summaries
                    WHERE commit_hash = ANY(:commit_hashes)
                    """
                ),
                {"commit_hashes": commit_hashes},
            ).fetchall()

        summaries: Dict[str, Dict] = {}
        for row in rows:
            summaries[row[0]] = {
                "hash": row[0],
                "message": row[1],
                "summary": row[2],
                "status": row[3],
                "error": row[4],
            }
        return summaries

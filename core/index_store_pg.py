"""PostgreSQL-backed storage for repository and commit metadata indexes."""

from __future__ import annotations

import json
from typing import Dict, List, Optional

from sqlalchemy import text

from .db import get_engine


class PostgresIndexStore:
    """Persistent commit index storage in PostgreSQL."""

    def __init__(self):
        self.engine = get_engine()
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        with self.engine.begin() as connection:
            connection.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS repositories (
                        id BIGSERIAL PRIMARY KEY,
                        repo_path TEXT UNIQUE NOT NULL,
                        name TEXT NOT NULL,
                        indexed_at TIMESTAMPTZ,
                        total_commits INTEGER NOT NULL DEFAULT 0,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                        updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
                    )
                    """
                )
            )
            connection.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS commits (
                        id BIGSERIAL PRIMARY KEY,
                        repository_id BIGINT NOT NULL REFERENCES repositories(id) ON DELETE CASCADE,
                        commit_hash TEXT NOT NULL,
                        short_hash TEXT,
                        message TEXT NOT NULL,
                        author TEXT,
                        committed_at TIMESTAMPTZ NOT NULL,
                        files JSONB NOT NULL DEFAULT '[]'::jsonb,
                        metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                        updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                        UNIQUE (repository_id, commit_hash)
                    )
                    """
                )
            )
            connection.execute(
                text(
                    """
                    CREATE INDEX IF NOT EXISTS idx_repositories_repo_path
                    ON repositories (repo_path)
                    """
                )
            )
            connection.execute(
                text(
                    """
                    CREATE INDEX IF NOT EXISTS idx_commits_repo_time
                    ON commits (repository_id, committed_at DESC)
                    """
                )
            )

    @staticmethod
    def _repo_name_from_path(repo_path: str) -> str:
        normalized = repo_path.rstrip("/")
        if not normalized:
            return "unknown"
        return normalized.split("/")[-1]

    def _upsert_repository(self, repo_path: str, total_commits: Optional[int] = None) -> int:
        repo_name = self._repo_name_from_path(repo_path)

        with self.engine.begin() as connection:
            row = connection.execute(
                text(
                    """
                    INSERT INTO repositories (repo_path, name, indexed_at, total_commits, updated_at)
                    VALUES (:repo_path, :name, now(), COALESCE(:total_commits, 0), now())
                    ON CONFLICT (repo_path)
                    DO UPDATE SET
                        name = EXCLUDED.name,
                        indexed_at = now(),
                        total_commits = COALESCE(:total_commits, repositories.total_commits),
                        updated_at = now()
                    RETURNING id
                    """
                ),
                {
                    "repo_path": repo_path,
                    "name": repo_name,
                    "total_commits": total_commits,
                },
            ).one()

            return int(row[0])

    def replace_commits(self, repo_path: str, commits: List[Dict]) -> None:
        repository_id = self._upsert_repository(repo_path, total_commits=len(commits))

        with self.engine.begin() as connection:
            connection.execute(
                text("DELETE FROM commits WHERE repository_id = :repository_id"),
                {"repository_id": repository_id},
            )

            for commit in commits:
                commit_hash = commit.get("hash")
                if not commit_hash:
                    continue

                connection.execute(
                    text(
                        """
                        INSERT INTO commits (
                            repository_id,
                            commit_hash,
                            short_hash,
                            message,
                            author,
                            committed_at,
                            files,
                            metadata,
                            updated_at
                        ) VALUES (
                            :repository_id,
                            :commit_hash,
                            :short_hash,
                            :message,
                            :author,
                            CAST(:committed_at AS timestamptz),
                            CAST(:files AS jsonb),
                            CAST(:metadata AS jsonb),
                            now()
                        )
                        """
                    ),
                    {
                        "repository_id": repository_id,
                        "commit_hash": commit_hash,
                        "short_hash": commit.get("short_hash", commit_hash[:8]),
                        "message": commit.get("message", ""),
                        "author": commit.get("author", "Unknown"),
                        "committed_at": commit.get("date"),
                        "files": json.dumps(commit.get("files", [])),
                        "metadata": json.dumps(commit),
                    },
                )

    def load_commits(self, repo_path: str, max_commits: Optional[int] = None) -> List[Dict]:
        with self.engine.begin() as connection:
            repo_row = connection.execute(
                text("SELECT id FROM repositories WHERE repo_path = :repo_path"),
                {"repo_path": repo_path},
            ).one_or_none()

            if not repo_row:
                return []

            repository_id = int(repo_row[0])

            query = (
                """
                SELECT metadata
                FROM commits
                WHERE repository_id = :repository_id
                ORDER BY committed_at DESC
                """
            )
            params = {"repository_id": repository_id}
            if max_commits is not None:
                query += " LIMIT :limit"
                params["limit"] = max_commits

            rows = connection.execute(text(query), params).fetchall()

        commits: List[Dict] = []
        for row in rows:
            metadata = row[0]
            if isinstance(metadata, str):
                metadata = json.loads(metadata)
            commits.append(metadata)

        return commits

    def get_repository_stats(self, repo_path: str) -> Dict:
        with self.engine.begin() as connection:
            row = connection.execute(
                text(
                    """
                    SELECT id, total_commits, indexed_at
                    FROM repositories
                    WHERE repo_path = :repo_path
                    """
                ),
                {"repo_path": repo_path},
            ).one_or_none()

            if not row:
                return {"exists": False, "total_commits": 0, "indexed_at": None}

            return {
                "exists": True,
                "repository_id": int(row[0]),
                "total_commits": int(row[1] or 0),
                "indexed_at": row[2].isoformat() if row[2] is not None else None,
            }

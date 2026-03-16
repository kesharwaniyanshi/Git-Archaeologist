"""PostgreSQL-backed user store for GitHub OAuth identities."""

from __future__ import annotations

from typing import Dict, Optional

from sqlalchemy import text

from .db import get_engine


class PostgresAuthStore:
    """Persistent user identity storage."""

    def __init__(self):
        self.engine = get_engine()
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        with self.engine.begin() as connection:
            connection.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS users (
                        id BIGSERIAL PRIMARY KEY,
                        github_id TEXT UNIQUE NOT NULL,
                        login TEXT NOT NULL,
                        email TEXT,
                        name TEXT,
                        avatar_url TEXT,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                        updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
                    )
                    """
                )
            )
            connection.execute(
                text(
                    """
                    CREATE INDEX IF NOT EXISTS idx_users_github_id
                    ON users (github_id)
                    """
                )
            )

    def upsert_user(self, profile: Dict) -> Dict:
        github_id = str(profile.get("id", ""))
        if not github_id:
            raise ValueError("GitHub profile missing id")

        login = profile.get("login", "")
        if not login:
            raise ValueError("GitHub profile missing login")

        payload = {
            "github_id": github_id,
            "login": login,
            "email": profile.get("email"),
            "name": profile.get("name"),
            "avatar_url": profile.get("avatar_url"),
        }

        with self.engine.begin() as connection:
            row = connection.execute(
                text(
                    """
                    INSERT INTO users (github_id, login, email, name, avatar_url, created_at, updated_at)
                    VALUES (:github_id, :login, :email, :name, :avatar_url, now(), now())
                    ON CONFLICT (github_id)
                    DO UPDATE SET
                        login = EXCLUDED.login,
                        email = EXCLUDED.email,
                        name = EXCLUDED.name,
                        avatar_url = EXCLUDED.avatar_url,
                        updated_at = now()
                    RETURNING id, github_id, login, email, name, avatar_url
                    """
                ),
                payload,
            ).one()

        return {
            "id": int(row[0]),
            "github_id": row[1],
            "login": row[2],
            "email": row[3],
            "name": row[4],
            "avatar_url": row[5],
        }

    def get_user_by_github_id(self, github_id: str) -> Optional[Dict]:
        with self.engine.begin() as connection:
            row = connection.execute(
                text(
                    """
                    SELECT id, github_id, login, email, name, avatar_url
                    FROM users
                    WHERE github_id = :github_id
                    """
                ),
                {"github_id": github_id},
            ).one_or_none()

        if not row:
            return None

        return {
            "id": int(row[0]),
            "github_id": row[1],
            "login": row[2],
            "email": row[3],
            "name": row[4],
            "avatar_url": row[5],
        }

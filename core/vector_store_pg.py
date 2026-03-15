"""PostgreSQL pgvector-backed vector store.

This module provides a FAISS-compatible interface used by the analyzer:
- add_embeddings(...)
- search(...)
- save(...)
- load(...)
- size()
- clear()
"""

from __future__ import annotations

import json
from typing import Dict, List, Optional, Tuple

from sqlalchemy import text

from .db import get_engine


class PostgresVectorStore:
    """Persistent vector store using PostgreSQL + pgvector."""

    def __init__(self, dimension: int = 384):
        self.dimension = dimension
        self.engine = get_engine()
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        with self.engine.begin() as connection:
            connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            connection.execute(
                text(
                    f"""
                    CREATE TABLE IF NOT EXISTS commit_embeddings (
                        commit_hash TEXT PRIMARY KEY,
                        embedding vector({self.dimension}) NOT NULL,
                        metadata JSONB NOT NULL,
                        created_at TIMESTAMPTZ DEFAULT now()
                    )
                    """
                )
            )
            connection.execute(
                text(
                    """
                    CREATE INDEX IF NOT EXISTS idx_commit_embeddings_ivfflat
                    ON commit_embeddings USING ivfflat (embedding vector_cosine_ops)
                    WITH (lists = 100)
                    """
                )
            )

    def add_embeddings(self, embeddings: List[List[float]], metadata: Dict[str, Dict]) -> None:
        if not embeddings or not metadata:
            return

        if len(embeddings) != len(metadata):
            raise ValueError("Embeddings and metadata size mismatch.")

        # Keep insertion order aligned with how metadata is built from commits_index.
        items = list(metadata.items())
        with self.engine.begin() as connection:
            for idx, (commit_hash, commit_meta) in enumerate(items):
                vector = embeddings[idx]
                if len(vector) != self.dimension:
                    raise ValueError(
                        f"Embedding dimension mismatch for {commit_hash}: expected {self.dimension}, got {len(vector)}"
                    )

                connection.execute(
                    text(
                        """
                        INSERT INTO commit_embeddings (commit_hash, embedding, metadata)
                        VALUES (:commit_hash, CAST(:embedding AS vector), CAST(:metadata AS jsonb))
                        ON CONFLICT (commit_hash)
                        DO UPDATE SET
                            embedding = EXCLUDED.embedding,
                            metadata = EXCLUDED.metadata
                        """
                    ),
                    {
                        "commit_hash": commit_hash,
                        "embedding": json.dumps(vector),
                        "metadata": json.dumps(commit_meta),
                    },
                )

    def search(self, query_embedding: List[float], top_k: int = 20) -> List[Tuple[str, float, Dict]]:
        if not query_embedding:
            return []

        with self.engine.begin() as connection:
            rows = connection.execute(
                text(
                    """
                    SELECT
                        commit_hash,
                        metadata,
                        (embedding <=> CAST(:query_embedding AS vector)) AS distance
                    FROM commit_embeddings
                    ORDER BY embedding <=> CAST(:query_embedding AS vector)
                    LIMIT :top_k
                    """
                ),
                {
                    "query_embedding": json.dumps(query_embedding),
                    "top_k": top_k,
                },
            ).fetchall()

        results: List[Tuple[str, float, Dict]] = []
        for row in rows:
            commit_hash = row[0]
            meta = row[1]
            distance = row[2]
            if isinstance(meta, str):
                meta = json.loads(meta)

            # Convert cosine distance to a similarity-like score for compatibility.
            similarity = max(0.0, 1.0 - float(distance))
            results.append((commit_hash, similarity, meta))

        return results

    def save(self, save_dir: str) -> None:
        # No-op: persistence is handled by PostgreSQL.
        _ = save_dir

    def load(self, load_dir: str) -> None:
        # No-op: data is read directly from PostgreSQL.
        _ = load_dir

    def size(self) -> int:
        with self.engine.begin() as connection:
            count = connection.execute(text("SELECT COUNT(*) FROM commit_embeddings")).scalar_one()
            return int(count)

    def clear(self) -> None:
        with self.engine.begin() as connection:
            connection.execute(text("TRUNCATE TABLE commit_embeddings"))

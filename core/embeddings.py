"""
Embeddings utilities for semantic commit retrieval.

Uses sentence-transformers locally and provides commit text building + ranking.
"""

from __future__ import annotations

from typing import Dict, List


class EmbeddingEngine:
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise ImportError(
                "sentence-transformers is not installed. "
                "Run: pip install sentence-transformers"
            ) from exc

        self.model_name = model_name
        self.model = SentenceTransformer(model_name)

    def encode_texts(self, texts: List[str]) -> List[List[float]]:
        vectors = self.model.encode(
            texts,
            normalize_embeddings=True,
            show_progress_bar=False,
            convert_to_numpy=True,
        )
        return vectors.tolist()


def build_commit_semantic_text(commit: Dict) -> str:
    """
    Build a compact semantic representation of a commit for embedding.
    """
    message = commit.get("message", "")
    files = commit.get("files", []) or []
    file_names = []
    for f in files[:20]:
        if isinstance(f, dict):
            file_names.append(f.get("filename", ""))
        else:
            file_names.append(str(f))
    file_blob = " ".join(file_names)
    return f"message: {message}\nfiles: {file_blob}".strip()


def cosine_similarity(a: List[float], b: List[float]) -> float:
    """
    Cosine similarity for normalized vectors.
    """
    if not a or not b or len(a) != len(b):
        return 0.0
    return float(sum(x * y for x, y in zip(a, b)))


def rank_commits_by_semantic(
    query: str,
    commits: List[Dict],
    commit_embeddings: List[List[float]],
    embedding_engine: EmbeddingEngine,
    top_n: int = 20,
) -> List[Dict]:
    """
    Rank commits by semantic similarity between query and commit embeddings.
    """
    if not commits or not commit_embeddings:
        return []

    query_vec = embedding_engine.encode_texts([query])[0]
    scored = []

    for commit, vector in zip(commits, commit_embeddings):
        score = cosine_similarity(query_vec, vector)
        scored.append((score, commit))

    scored.sort(key=lambda item: item[0], reverse=True)
    return [commit for _, commit in scored[:top_n]]

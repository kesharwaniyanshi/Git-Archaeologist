"""Data models for retrieval pipeline outputs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional


@dataclass
class RetrievalResult:
    commit_hash: str
    short_hash: str
    message: str
    summary: str
    author: str
    date: str
    relevance_score: float
    status: str
    error: Optional[str] = None

    def to_dict(self) -> Dict:
        return {
            "commit_hash": self.commit_hash,
            "short_hash": self.short_hash,
            "message": self.message,
            "summary": self.summary,
            "author": self.author,
            "date": self.date,
            "relevance_score": self.relevance_score,
            "status": self.status,
            "error": self.error,
        }


@dataclass
class QueryMetadata:
    query: str
    timestamp: str
    candidates_evaluated: int
    summaries_generated: int
    cache_hits: int
    elapsed_seconds: float

    def to_dict(self) -> Dict:
        return {
            "query": self.query,
            "timestamp": self.timestamp,
            "candidates_evaluated": self.candidates_evaluated,
            "summaries_generated": self.summaries_generated,
            "cache_hits": self.cache_hits,
            "elapsed_seconds": self.elapsed_seconds,
        }

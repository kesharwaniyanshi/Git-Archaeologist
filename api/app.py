"""
FastAPI service for Git Archaeologist.

Endpoints:
- GET /health
- GET /status
- POST /index
- POST /analyze
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from analyzers.query_analyzer import QueryDrivenAnalyzer
from pipelines.rag_pipeline import RAGPipeline


app = FastAPI(
    title="Git Archaeologist API",
    version="0.1.0",
    description="Query-driven Git history analysis with retrieval + synthesized answers.",
)


@dataclass
class AnalyzerHandle:
    key: str
    analyzer: QueryDrivenAnalyzer


class IndexRequest(BaseModel):
    repo_path: str = Field(..., description="Local path to git repository")
    session_dir: Optional[str] = Field(default=None, description="Session directory for persistence")
    max_commits: int = Field(default=500, ge=1, le=20000)
    use_embeddings: bool = True
    embedding_model: str = "all-MiniLM-L6-v2"
    force_reindex: bool = False


class AnalyzeRequest(BaseModel):
    repo_path: str = Field(..., description="Local path to git repository")
    query: str = Field(..., min_length=3)
    session_dir: Optional[str] = Field(default=None, description="Session directory for persistence")
    max_commits: int = Field(default=500, ge=1, le=20000)
    top_k: int = Field(default=5, ge=1, le=50)
    analyze_candidates: int = Field(default=20, ge=1, le=200)
    use_embeddings: bool = True
    embedding_model: str = "all-MiniLM-L6-v2"
    boost_freshness: bool = True
    show_evidence: bool = False


class AnalyzeResponse(BaseModel):
    query: str
    answer: str
    evidence_count: int
    evidence: Optional[List[Dict]] = None


class AnalyzerRegistry:
    def __init__(self):
        self._handles: Dict[str, AnalyzerHandle] = {}

    @staticmethod
    def _key(repo_path: str, session_dir: Optional[str], embedding_model: str, use_embeddings: bool) -> str:
        return "|".join([
            repo_path,
            session_dir or ".git_arch_sessions/default",
            embedding_model,
            str(use_embeddings),
        ])

    def get_or_create(
        self,
        repo_path: str,
        session_dir: Optional[str],
        use_embeddings: bool,
        embedding_model: str,
    ) -> QueryDrivenAnalyzer:
        key = self._key(repo_path, session_dir, embedding_model, use_embeddings)

        if key in self._handles:
            return self._handles[key].analyzer

        analyzer = QueryDrivenAnalyzer(
            repo_path=repo_path,
            use_embeddings=use_embeddings,
            embedding_model=embedding_model,
            session_dir=session_dir,
        )
        self._handles[key] = AnalyzerHandle(key=key, analyzer=analyzer)
        return analyzer

    def status(self) -> Dict:
        sessions = []
        for key, handle in self._handles.items():
            sessions.append(
                {
                    "key": key,
                    "repo_path": handle.analyzer.repo_path,
                    "session_dir": str(handle.analyzer.session_dir),
                    "indexed_commits": len(handle.analyzer.commits_index),
                    "cached_summaries": len(handle.analyzer.summary_cache),
                    "embeddings_enabled": handle.analyzer.use_embeddings,
                }
            )
        return {"active_sessions": len(sessions), "sessions": sessions}


registry = AnalyzerRegistry()


def _ensure_index(analyzer: QueryDrivenAnalyzer, max_commits: int, force_reindex: bool = False) -> Dict:
    if force_reindex:
        stats = analyzer.index_repository(max_commits=max_commits)
        analyzer.save_session()
        return stats

    # Try loading persisted session first.
    loaded = analyzer.load_session()
    if loaded and analyzer.commits_index:
        return {
            "total_commits": len(analyzer.commits_index),
            "loaded_from_session": True,
            "cached_summaries": len(analyzer.summary_cache),
        }

    stats = analyzer.index_repository(max_commits=max_commits)
    analyzer.save_session()
    return stats


@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.get("/status")
def status() -> Dict:
    return registry.status()


@app.post("/index")
def index_repo(request: IndexRequest) -> Dict:
    try:
        analyzer = registry.get_or_create(
            repo_path=request.repo_path,
            session_dir=request.session_dir,
            use_embeddings=request.use_embeddings,
            embedding_model=request.embedding_model,
        )
        stats = _ensure_index(analyzer, request.max_commits, request.force_reindex)
        return {
            "message": "Repository indexed",
            "repo_path": request.repo_path,
            "session_dir": str(analyzer.session_dir),
            "stats": stats,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Indexing failed: {exc}")


@app.post("/analyze", response_model=AnalyzeResponse)
def analyze_query(request: AnalyzeRequest) -> AnalyzeResponse:
    try:
        analyzer = registry.get_or_create(
            repo_path=request.repo_path,
            session_dir=request.session_dir,
            use_embeddings=request.use_embeddings,
            embedding_model=request.embedding_model,
        )

        _ensure_index(analyzer, request.max_commits, force_reindex=False)

        rag = RAGPipeline(analyzer=analyzer, verbose=False)
        results = rag.retrieve(
            query=request.query,
            top_k=request.top_k,
            analyze_candidates=request.analyze_candidates,
            boost_freshness=request.boost_freshness,
        )
        answer = rag.synthesize_answer(request.query, results)

        evidence = [r.to_dict() for r in results] if request.show_evidence else None
        return AnalyzeResponse(
            query=request.query,
            answer=answer,
            evidence_count=len(results),
            evidence=evidence,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {exc}")

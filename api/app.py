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
import os

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from analyzers.query_analyzer import QueryDrivenAnalyzer
from pipelines.rag_pipeline import RAGPipeline


app = FastAPI(
    title="Git Archaeologist API",
    version="0.1.0",
    description="Query-driven Git history analysis with retrieval + synthesized answers.",
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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
    chat_session_id: Optional[str] = Field(default=None, description="Existing chat session identifier")
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
    chat_session_id: Optional[str] = None
    evidence_count: int
    evidence: Optional[List[Dict]] = None


class ChatSessionCreateRequest(BaseModel):
    repo_path: Optional[str] = Field(default=None, description="Local path to git repository")


class ChatSessionCreateResponse(BaseModel):
    chat_session_id: str


class ChatHistoryResponse(BaseModel):
    chat_session_id: str
    messages: List[Dict]


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


def _create_chat_store():
    # Keep chat persistence optional to avoid breaking local-only setups.
    if not os.getenv("DATABASE_URL"):
        return None
    try:
        from core.chat_store_pg import PostgresChatStore

        return PostgresChatStore()
    except Exception as exc:
        print(f"Chat store disabled: {exc}")
        return None


chat_store = _create_chat_store()


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

        response_chat_session_id = request.chat_session_id
        if chat_store:
            try:
                if not response_chat_session_id or not chat_store.session_exists(response_chat_session_id):
                    response_chat_session_id = chat_store.create_session(repo_path=request.repo_path)

                chat_store.append_message(
                    response_chat_session_id,
                    role="user",
                    content=request.query,
                    message_metadata={
                        "repo_path": request.repo_path,
                        "top_k": request.top_k,
                        "analyze_candidates": request.analyze_candidates,
                    },
                )
                chat_store.append_message(
                    response_chat_session_id,
                    role="assistant",
                    content=answer,
                    message_metadata={
                        "evidence_count": len(results),
                    },
                )
            except Exception as exc:
                # Do not fail answer generation if chat persistence fails.
                print(f"Failed to persist chat history: {exc}")

        evidence = [r.to_dict() for r in results] if request.show_evidence else None
        return AnalyzeResponse(
            query=request.query,
            answer=answer,
            chat_session_id=response_chat_session_id,
            evidence_count=len(results),
            evidence=evidence,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {exc}")


@app.post("/chat/session", response_model=ChatSessionCreateResponse)
def create_chat_session(request: ChatSessionCreateRequest) -> ChatSessionCreateResponse:
    if not chat_store:
        raise HTTPException(status_code=503, detail="Chat persistence is not configured")

    try:
        session_id = chat_store.create_session(repo_path=request.repo_path)
        return ChatSessionCreateResponse(chat_session_id=session_id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to create chat session: {exc}")


@app.get("/chat/{chat_session_id}", response_model=ChatHistoryResponse)
def get_chat_history(chat_session_id: str) -> ChatHistoryResponse:
    if not chat_store:
        raise HTTPException(status_code=503, detail="Chat persistence is not configured")

    try:
        if not chat_store.session_exists(chat_session_id):
            raise HTTPException(status_code=404, detail="Chat session not found")

        messages = chat_store.get_messages(chat_session_id)
        return ChatHistoryResponse(chat_session_id=chat_session_id, messages=messages)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to load chat history: {exc}")

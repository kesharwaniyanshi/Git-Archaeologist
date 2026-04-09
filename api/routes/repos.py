import structlog
from fastapi import APIRouter, HTTPException
from typing import Dict
from core.models.api import IndexRequest, AnalyzeRequest, AnalyzeResponse
from core.services.registry import get_registry
from core.github_fetcher import GitHubFetcherError, is_github_repo_url
from pipelines.rag_pipeline import RAGPipeline
from api.dependencies import get_chat_store

logger = structlog.get_logger()
router = APIRouter(tags=["repos"])

def _ensure_index(analyzer, max_commits: int, force_reindex: bool = False) -> Dict:
    github_mode = is_github_repo_url(analyzer.repo_path)
    if force_reindex:
        stats = analyzer.index_repository(max_commits=max_commits)
        if not github_mode:
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
    if not github_mode:
        analyzer.save_session()
    return stats

@router.post("/index")
def index_repo(request: IndexRequest) -> Dict:
    registry = get_registry()
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
    except GitHubFetcherError as exc:
        logger.warning("github_fetcher_error", error=str(exc), repo_path=request.repo_path)
        raise HTTPException(status_code=exc.status_code, detail=str(exc))
    except Exception as exc:
        logger.error("indexing_failed", error=str(exc), repo_path=request.repo_path)
        raise HTTPException(status_code=500, detail=f"Indexing failed: {exc}")

@router.post("/analyze", response_model=AnalyzeResponse)
def analyze_query(request: AnalyzeRequest) -> AnalyzeResponse:
    registry = get_registry()
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
        chat_store = get_chat_store()
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
                logger.error("chat_persist_failed", error=str(exc))

        evidence = [r.to_dict() for r in results] if request.show_evidence else None
        return AnalyzeResponse(
            query=request.query,
            answer=answer,
            chat_session_id=response_chat_session_id,
            evidence_count=len(results),
            evidence=evidence,
        )
    except GitHubFetcherError as exc:
        logger.warning("github_fetcher_error", error=str(exc))
        raise HTTPException(status_code=exc.status_code, detail=str(exc))
    except Exception as exc:
        logger.error("analysis_failed", error=str(exc))
        raise HTTPException(status_code=500, detail=f"Analysis failed: {exc}")

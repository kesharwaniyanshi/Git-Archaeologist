import structlog
from typing import Optional
from fastapi import APIRouter, HTTPException
from core.models.api import ChatSessionCreateRequest, ChatSessionCreateResponse, ChatHistoryResponse, ChatSessionListResponse, ChatSessionListItem
from api.dependencies import get_chat_store

logger = structlog.get_logger()
router = APIRouter(prefix="/chat", tags=["chat"])

@router.post("/session", response_model=ChatSessionCreateResponse)
def create_chat_session(request: ChatSessionCreateRequest) -> ChatSessionCreateResponse:
    chat_store = get_chat_store()
    if not chat_store:
        raise HTTPException(status_code=503, detail="Chat persistence is not configured")

    try:
        session_id = chat_store.create_session(repo_path=request.repo_path)
        return ChatSessionCreateResponse(chat_session_id=session_id)
    except Exception as exc:
        logger.error("create_chat_session_failed", error=str(exc))
        raise HTTPException(status_code=500, detail=f"Failed to create chat session: {exc}")

@router.get("/{chat_session_id}", response_model=ChatHistoryResponse)
def get_chat_history(chat_session_id: str) -> ChatHistoryResponse:
    chat_store = get_chat_store()
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
        logger.error("get_chat_history_failed", error=str(exc), chat_session_id=chat_session_id)
        raise HTTPException(status_code=500, detail=f"Failed to load chat history: {exc}")

@router.get("", response_model=ChatSessionListResponse)
def list_chat_sessions(repo_path: Optional[str] = None, limit: int = 50) -> ChatSessionListResponse:
    chat_store = get_chat_store()
    if not chat_store:
        raise HTTPException(status_code=503, detail="Chat persistence is not configured")

    try:
        sessions = chat_store.list_sessions(repo_path=repo_path, limit=max(1, min(200, limit)))
        return ChatSessionListResponse(sessions=[ChatSessionListItem(**item) for item in sessions])
    except Exception as exc:
        logger.error("list_chat_sessions_failed", error=str(exc))
        raise HTTPException(status_code=500, detail=f"Failed to list chat sessions: {exc}")

"""Chat session routes with persistent message storage and RAG pipeline integration."""

import structlog
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func as sa_func

from core.models.api import (
    ChatSessionCreateRequest,
    ChatSessionCreateResponse,
    ChatHistoryResponse,
    ChatSessionListResponse,
    ChatSessionListItem,
    ChatMessageItem,
    SendMessageRequest,
    SendMessageResponse,
)
from db.models import ChatSession, ChatMessage
from api.dependencies import get_db, get_current_user

logger = structlog.get_logger()
router = APIRouter(prefix="/chat", tags=["chat"])


def _require_user(user):
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user


@router.post("/sessions", response_model=ChatSessionCreateResponse)
def create_chat_session(
    request: ChatSessionCreateRequest,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    user = _require_user(user)
    session = ChatSession(
        user_id=user.id,
        repository_id=request.repository_id,
        title=None,  # Auto-set on first message
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return ChatSessionCreateResponse(chat_session_id=session.id, title=session.title)


@router.get("/sessions", response_model=ChatSessionListResponse)
def list_chat_sessions(
    limit: int = 50,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    user = _require_user(user)
    sessions = (
        db.query(ChatSession)
        .filter(ChatSession.user_id == user.id)
        .order_by(ChatSession.updated_at.desc())
        .limit(min(limit, 100))
        .all()
    )

    session_ids = [s.id for s in sessions]
    msg_count_map = {}
    if session_ids:
        count_rows = (
            db.query(ChatMessage.session_id, sa_func.count(ChatMessage.id))
            .filter(ChatMessage.session_id.in_(session_ids))
            .group_by(ChatMessage.session_id)
            .all()
        )
        msg_count_map = {session_id: count for session_id, count in count_rows}

    items = []
    for s in sessions:
        items.append(
            ChatSessionListItem(
                chat_session_id=s.id,
                title=s.title,
                created_at=s.created_at.isoformat() if s.created_at else None,
                updated_at=s.updated_at.isoformat() if s.updated_at else None,
                message_count=msg_count_map.get(s.id, 0),
            )
        )

    return ChatSessionListResponse(sessions=items)


@router.get("/sessions/{session_id}", response_model=ChatHistoryResponse)
def get_chat_history(
    session_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    user = _require_user(user)
    session = db.query(ChatSession).filter(
        ChatSession.id == session_id,
        ChatSession.user_id == user.id,
    ).first()

    if not session:
        raise HTTPException(status_code=404, detail="Chat session not found")

    messages = (
        db.query(ChatMessage)
        .filter(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at.asc())
        .all()
    )

    return ChatHistoryResponse(
        chat_session_id=session.id,
        title=session.title,
        messages=[
            ChatMessageItem(
                id=m.id,
                role=m.role,
                content=m.content,
                created_at=m.created_at.isoformat() if m.created_at else "",
            )
            for m in messages
        ],
    )


@router.post("/sessions/{session_id}/messages", response_model=SendMessageResponse)
def send_message(
    session_id: str,
    request: SendMessageRequest,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    user = _require_user(user)
    session = db.query(ChatSession).filter(
        ChatSession.id == session_id,
        ChatSession.user_id == user.id,
    ).first()

    if not session:
        raise HTTPException(status_code=404, detail="Chat session not found")

    # 1. Save user message
    user_msg = ChatMessage(session_id=session.id, role="user", content=request.content)
    db.add(user_msg)

    # Auto-set session title from first user message
    if not session.title:
        session.title = request.content[:80]

    db.commit()
    db.refresh(user_msg)

    # 2. Load conversation history (last 10 messages for context)
    prior_messages = (
        db.query(ChatMessage)
        .filter(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at.asc())
        .all()
    )
    conversation_history = [
        {"role": m.role, "content": m.content}
        for m in prior_messages[-10:]
    ]

    # 3. Generate AI response via RAG pipeline
    answer_text = _generate_answer(
        request.content,
        conversation_history,
        session.repository_id,
        db,
        user,
    )

    # 4. Save assistant message
    assistant_msg = ChatMessage(session_id=session.id, role="assistant", content=answer_text)
    db.add(assistant_msg)

    # Touch updated_at
    session.updated_at = sa_func.now()
    db.commit()
    db.refresh(assistant_msg)

    return SendMessageResponse(
        user_message=ChatMessageItem(
            id=user_msg.id,
            role=user_msg.role,
            content=user_msg.content,
            created_at=user_msg.created_at.isoformat() if user_msg.created_at else "",
        ),
        assistant_message=ChatMessageItem(
            id=assistant_msg.id,
            role=assistant_msg.role,
            content=assistant_msg.content,
            created_at=assistant_msg.created_at.isoformat() if assistant_msg.created_at else "",
        ),
    )


def _generate_answer(
    query: str,
    conversation_history: list,
    repository_id: Optional[str],
    db: Session,
    user,
) -> str:
    """Run the RAG pipeline to generate an answer, falling back to direct LLM if no repo is indexed."""
    try:
        from analyzers.contributor_intent import build_author_predicate, parse_contributor_query
        from core.services.registry import get_registry

        registry = get_registry()
        contributor_intent = parse_contributor_query(query)
        commit_filter = None
        contributor_mode = False
        contributor_label = ""

        if contributor_intent:
            if contributor_intent.self_query:
                if not user:
                    return (
                        "To summarize your contributions, sign in. "
                        "Your commits are matched using the email on your account and the author email stored for each commit."
                    )
                if not getattr(user, "email", None):
                    return (
                        "Your account has no email on file, so your commits cannot be matched automatically. "
                        "Try naming a contributor or including an email that appears in Git history."
                    )
            predicate = build_author_predicate(contributor_intent, user)
            if contributor_intent.self_query and predicate is None:
                return (
                    "Could not match your account to commits. Ensure your login email matches the Git author email "
                    "used in this repository."
                )
            if predicate is not None:
                commit_filter = predicate
                contributor_mode = True
                contributor_label = contributor_intent.label_for_prompt()

        # If a repository is linked, try to use the RAG pipeline
        if repository_id:
            from db.models import Repository
            repo = db.query(Repository).filter(Repository.id == repository_id).first()
            if repo and repo.url:
                try:
                    analyzer = registry.get_or_create(
                        repo_path=repo.url,
                        session_dir=None,
                        use_embeddings=True,
                        embedding_model="all-MiniLM-L6-v2",
                    )
                    
                    if not analyzer.commits_index:
                        analyzer.load_session()
                        
                    if analyzer and analyzer.commits_index:
                        from pipelines.rag_pipeline import RAGPipeline
                        pipeline = RAGPipeline(analyzer, verbose=False)
                        results = pipeline.retrieve(
                            query,
                            top_k=10,
                            analyze_candidates=20,
                            commit_filter=commit_filter,
                        )
                        logger.info(
                            "rag_retrieval_complete",
                            repository_id=repository_id,
                            contributor_mode=contributor_mode,
                            result_count=len(results),
                        )
                        if contributor_mode and not results:
                            return (
                                "No commits in this repository's index match that contributor. "
                                "For your own work, use the same email in Git as on your account, or ask using a name "
                                "or email from the commit history."
                            )
                        return pipeline.synthesize_answer(
                            query,
                            results,
                            conversation_history,
                            contributor_mode=contributor_mode,
                            contributor_label=contributor_label,
                        )
                except Exception as exc:
                    logger.warning("rag_pipeline_failed", error=str(exc))

        # Fallback: Use the LLM directly with conversation context
        from core.summarizer import CommitSummarizer
        summarizer = CommitSummarizer()

        history_text = ""
        if conversation_history:
            history_lines = []
            for turn in conversation_history[-6:]:
                role = turn.get("role", "user")
                content = turn.get("content", "")
                if content:
                    history_lines.append(f"{role.upper()}: {content[:500]}")
            if history_lines:
                history_text = "Previous conversation:\n" + "\n".join(history_lines) + "\n\n"

        system_prompt = (
            "You are Git Archaeologist, an expert software forensics assistant. "
            "You help developers understand code history and repository evolution. "
            "If no repository evidence is available, explain what you would need to answer properly. "
            "Be conversational and helpful. If this is a follow-up question, use the conversation context."
        )
        user_prompt = f"{history_text}Question: {query}"

        return summarizer._call_groq_synthesis(system_prompt, user_prompt)

    except Exception as exc:
        logger.error("answer_generation_failed", error=str(exc))
        return f"I encountered an error generating an answer: {str(exc)}. Please try again."

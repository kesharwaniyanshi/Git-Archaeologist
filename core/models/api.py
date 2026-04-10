from typing import Dict, List, Optional
from pydantic import BaseModel, Field

class LinkRepoRequest(BaseModel):
    url: str = Field(..., description="Public GitHub repository URL or owner/repo format")

class RepositoryResponse(BaseModel):
    id: str
    url: str
    owner: str
    name: str
    last_indexed_commit: Optional[str] = None
    created_at: str

class IndexRequest(BaseModel):
    repo_path: str = Field(..., description="Public GitHub repository URL")
    use_embeddings: bool = True
    embedding_model: str = "all-MiniLM-L6-v2"
    force_reindex: bool = False

class AnalyzeRequest(BaseModel):
    repo_path: str = Field(..., description="Public GitHub repository URL")
    query: str = Field(..., min_length=3)
    chat_session_id: Optional[str] = Field(default=None, description="Existing chat session identifier")
    session_dir: Optional[str] = Field(default=None, description="Session directory for persistence")
    max_commits: int = Field(default=500, ge=1, le=20000)
    top_k: int = Field(default=10, ge=1, le=50)
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
    repository_id: Optional[str] = Field(default=None, description="Optional repository to scope this session to")

class ChatSessionCreateResponse(BaseModel):
    chat_session_id: str
    title: Optional[str] = None

class ChatMessageItem(BaseModel):
    id: str
    role: str
    content: str
    created_at: str

class ChatHistoryResponse(BaseModel):
    chat_session_id: str
    title: Optional[str] = None
    messages: List[ChatMessageItem]

class ChatSessionListItem(BaseModel):
    chat_session_id: str
    title: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    message_count: int = 0

class ChatSessionListResponse(BaseModel):
    sessions: List[ChatSessionListItem]

class SendMessageRequest(BaseModel):
    content: str = Field(..., min_length=1, description="User's message text")

class SendMessageResponse(BaseModel):
    user_message: ChatMessageItem
    assistant_message: ChatMessageItem

class AuthStatusResponse(BaseModel):
    authenticated: bool
    user: Optional[Dict] = None

class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    
class RegisterRequest(BaseModel):
    email: str = Field(..., min_length=5)
    password: str = Field(..., min_length=6)

class LoginRequest(BaseModel):
    email: str
    password: str

class UserResponse(BaseModel):
    id: str
    email: str
    github_id: Optional[str] = None
    google_id: Optional[str] = None

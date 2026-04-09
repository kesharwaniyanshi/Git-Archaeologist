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
    repo_path: Optional[str] = Field(default=None, description="Public GitHub repository URL")

class ChatSessionCreateResponse(BaseModel):
    chat_session_id: str

class ChatHistoryResponse(BaseModel):
    chat_session_id: str
    messages: List[Dict]

class ChatSessionListItem(BaseModel):
    chat_session_id: str
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    last_user_query: str = ""
    message_count: int = 0

class ChatSessionListResponse(BaseModel):
    sessions: List[ChatSessionListItem]

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

from sqlalchemy import Column, String, DateTime, ForeignKey, Integer, func
from sqlalchemy.orm import relationship
from db.session import Base
import uuid

class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=True) # Null if user strictly uses OAuth
    github_id = Column(String, unique=True, nullable=True)
    google_id = Column(String, unique=True, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Repository(Base):
    __tablename__ = "repositories"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    url = Column(String, nullable=False, unique=True)
    owner = Column(String, nullable=False)
    name = Column(String, nullable=False)
    last_indexed_commit = Column(String, nullable=True) # Checkpoint for fast-forward
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    commits = relationship("Commit", back_populates="repo", cascade="all, delete-orphan")

class Commit(Base):
    __tablename__ = "commits"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    repository_id = Column(String, ForeignKey("repositories.id", ondelete="CASCADE"), index=True)
    hash = Column(String, nullable=False, index=True)
    author_name = Column(String, nullable=True)
    author_email = Column(String, nullable=True)
    message = Column(String, nullable=True)
    timestamp = Column(DateTime(timezone=True), nullable=False)

    repo = relationship("Repository", back_populates="commits")
    diffs = relationship("FileDiff", back_populates="commit_record", cascade="all, delete-orphan")

class FileDiff(Base):
    __tablename__ = "file_diffs"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    commit_id = Column(String, ForeignKey("commits.id", ondelete="CASCADE"), index=True)
    file_path = Column(String, nullable=False, index=True)
    status = Column(String, nullable=False) # added, modified, removed
    diff_content = Column(String, nullable=True)

    commit_record = relationship("Commit", back_populates="diffs")

class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    repository_id = Column(String, ForeignKey("repositories.id", ondelete="SET NULL"), nullable=True)
    title = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    user = relationship("User")
    repository = relationship("Repository")
    messages = relationship("ChatMessage", back_populates="session", cascade="all, delete-orphan", order_by="ChatMessage.created_at")

class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String, ForeignKey("chat_sessions.id", ondelete="CASCADE"), index=True, nullable=False)
    role = Column(String, nullable=False)  # "user" or "assistant"
    content = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    session = relationship("ChatSession", back_populates="messages")

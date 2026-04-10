import os
import importlib
import structlog
import jwt
from typing import Optional, Generator
from fastapi import HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from starlette.requests import Request
from sqlalchemy.orm import Session
from db.session import SessionLocal

def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

security = HTTPBearer(auto_error=False)

def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db)
):
    if not credentials:
        return None
        
    from db.models import User
    token = credentials.credentials
    secret = os.getenv("JWT_SECRET", "dev-secret-key-change-in-prod")
    try:
        payload = jwt.decode(token, secret, algorithms=["HS256"])
        user_id = payload.get("sub")
        if not user_id:
            return None
        return db.query(User).filter(User.id == user_id).first()
    except Exception as exc:
        logger.warning("jwt_decode_failed", error=str(exc))
        return None

logger = structlog.get_logger()

_auth_store = None
_oauth_client = None

def _create_auth_store():
    if not os.getenv("DATABASE_URL"):
        return None
    try:
        from core.auth_store_pg import PostgresAuthStore
        return PostgresAuthStore()
    except Exception as exc:
        logger.warning("auth_store_disabled", error=str(exc))
        return None

def get_auth_store():
    global _auth_store
    if _auth_store is None:
        _auth_store = _create_auth_store()
    return _auth_store

def _create_oauth_client():
    client_id = os.getenv("GITHUB_CLIENT_ID")
    client_secret = os.getenv("GITHUB_CLIENT_SECRET")
    if not client_id or not client_secret:
        return None

    try:
        module = importlib.import_module("authlib.integrations.starlette_client")
        OAuth = getattr(module, "OAuth")
    except Exception as exc:
        logger.warning("oauth_client_disabled", error=str(exc))
        return None

    oauth = OAuth()
    oauth.register(
        name="github",
        client_id=client_id,
        client_secret=client_secret,
        authorize_url="https://github.com/login/oauth/authorize",
        access_token_url="https://github.com/login/oauth/access_token",
        api_base_url="https://api.github.com/",
        client_kwargs={"scope": "read:user user:email"},
    )

    google_id = os.getenv("GOOGLE_CLIENT_ID")
    google_secret = os.getenv("GOOGLE_CLIENT_SECRET")
    if google_id and google_secret:
        oauth.register(
            name="google",
            client_id=google_id,
            client_secret=google_secret,
            server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
            client_kwargs={"scope": "openid email profile"}
        )

    return oauth

def get_oauth_client():
    global _oauth_client
    if _oauth_client:
        return _oauth_client
    _oauth_client = _create_oauth_client()
    return _oauth_client

import os
import structlog
import jwt
from datetime import datetime, timedelta
from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import RedirectResponse
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from core.models.api import AuthStatusResponse, RegisterRequest, LoginRequest, TokenResponse
from api.dependencies import get_oauth_client, get_current_user, get_db
from db.models import User

logger = structlog.get_logger()
router = APIRouter(prefix="/auth", tags=["auth"])

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def create_access_token(user_id: str) -> str:
    secret = os.getenv("JWT_SECRET", "dev-secret-key-change-in-prod")
    payload = {
        "sub": user_id,
        "exp": datetime.utcnow() + timedelta(days=7)
    }
    return jwt.encode(payload, secret, algorithm="HS256")

@router.post("/register", response_model=TokenResponse)
def register(request: RegisterRequest, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == request.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
        
    user = User(
        email=request.email,
        hashed_password=pwd_context.hash(request.password)
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return TokenResponse(access_token=create_access_token(user.id), token_type="bearer")

@router.post("/login", response_model=TokenResponse)
def login(request: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == request.email).first()
    if not user or not user.hashed_password:
        raise HTTPException(status_code=401, detail="Invalid credentials")
        
    if not pwd_context.verify(request.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
        
    return TokenResponse(access_token=create_access_token(user.id), token_type="bearer")

@router.get("/me", response_model=AuthStatusResponse)
def auth_me(user: User = Depends(get_current_user)) -> AuthStatusResponse:
    if not user:
        return AuthStatusResponse(authenticated=False, user=None)
    
    user_data = {
        "id": user.id,
        "email": user.email,
        "github_id": user.github_id,
        "google_id": user.google_id
    }
    return AuthStatusResponse(authenticated=True, user=user_data)

@router.get("/github/login")
async def auth_github_login(request: Request):
    oauth = get_oauth_client()
    if not oauth or not hasattr(oauth, 'github'):
        raise HTTPException(status_code=503, detail="GitHub OAuth not configured")
    
    redirect_uri = str(request.url_for("auth_github_callback"))
    return await oauth.github.authorize_redirect(request, redirect_uri)

@router.get("/github/callback", name="auth_github_callback")
async def auth_github_callback(request: Request, db: Session = Depends(get_db)):
    oauth = get_oauth_client()
    if not oauth:
        raise HTTPException(status_code=503, detail="OAuth not configured")

    try:
        token = await oauth.github.authorize_access_token(request)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"OAuth verification failed. Invalid or expired token code. Did you configure real Client keys? Error: {e}")

    profile_resp = await oauth.github.get("user", token=token)
    profile = profile_resp.json()
    
    email = profile.get("email")
    if not email:
        emails_resp = await oauth.github.get("user/emails", token=token)
        emails = emails_resp.json()
        if isinstance(emails, list):
            primary = next((entry for entry in emails if entry.get("primary")), None)
            if primary: email = primary.get("email")
            
    github_id = str(profile.get("id"))
    if not email or not github_id:
        raise HTTPException(status_code=400, detail="Failed to fetch complete GitHub profile")
    
    user = db.query(User).filter(User.github_id == github_id).first()
    if not user:
        user = db.query(User).filter(User.email == email).first()
        if user:
            user.github_id = github_id
        else:
            user = User(email=email, github_id=github_id)
            db.add(user)
        db.commit()
        db.refresh(user)
        
    jwt_token = create_access_token(user.id)
    frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000")
    return RedirectResponse(url=f"{frontend_url}/?token={jwt_token}")

@router.get("/google/login")
async def auth_google_login(request: Request):
    oauth = get_oauth_client()
    if not oauth or not hasattr(oauth, 'google'):
        raise HTTPException(status_code=503, detail="Google OAuth not configured in .env")
    
    redirect_uri = str(request.url_for("auth_google_callback"))
    return await oauth.google.authorize_redirect(request, redirect_uri)

@router.get("/google/callback", name="auth_google_callback")
async def auth_google_callback(request: Request, db: Session = Depends(get_db)):
    oauth = get_oauth_client()
    if not oauth or not hasattr(oauth, 'google'):
        raise HTTPException(status_code=503, detail="OAuth not configured")

    try:
        token = await oauth.google.authorize_access_token(request)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"OAuth verification failed: {str(e)}")

    profile = token.get("userinfo")
    if not profile:
        raise HTTPException(status_code=400, detail="Failed to fetch Google profile")
    
    email = profile.get("email")
    google_id = profile.get("sub")
    if not email:
        raise HTTPException(status_code=400, detail="Google account has no email")
    
    user = db.query(User).filter(User.google_id == google_id).first()
    if not user:
        user = db.query(User).filter(User.email == email).first()
        if user:
            user.google_id = google_id
        else:
            user = User(email=email, google_id=google_id)
            db.add(user)
        db.commit()
        db.refresh(user)
        
    jwt_token = create_access_token(user.id)
    frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000")
    return RedirectResponse(url=f"{frontend_url}/?token={jwt_token}")

@router.post("/logout")
def auth_logout():
    return {"message": "logged_out. destroy token on client layer."}


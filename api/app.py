"""
FastAPI service for Git Archaeologist.
"""
from __future__ import annotations
import os

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
import structlog

# Load local .env so OAuth and DB settings work without shell export.
load_dotenv()

# Set up structured logging using JSON
structlog.configure(
    processors=[
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ]
)
logger = structlog.get_logger()

from api.routes import auth, chat, repos
from core.services.registry import get_registry

from db.session import engine, Base
import db.models
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Git Archaeologist API",
    version="0.1.0",
    description="Query-driven Git history analysis with retrieval + synthesized answers.",
)

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

app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("APP_SESSION_SECRET", "dev-insecure-change-me"),
    same_site="lax",
    https_only=False,
)

# Include separated routers
app.include_router(auth.router)
app.include_router(chat.router)
app.include_router(repos.router)
w
@app.get("/health")
def health() -> dict:
    return {"status": "ok"}

@app.get("/status")
def status() -> dict:
    registry = get_registry()
    return registry.status()

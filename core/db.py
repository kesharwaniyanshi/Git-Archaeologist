"""Database setup for PostgreSQL-backed persistence."""

from __future__ import annotations

import os

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker


def get_database_url() -> str:
    database_url = os.getenv("DATABASE_URL", "")
    if not database_url:
        raise ValueError("DATABASE_URL is not set. Configure it in your environment.")
    if database_url.startswith("postgresql://"):
        # Accept common Postgres URL form and force psycopg driver for SQLAlchemy.
        database_url = "postgresql+psycopg://" + database_url[len("postgresql://"):]
    return database_url


def get_engine() -> Engine:
    return create_engine(get_database_url(), future=True)


def get_session_factory() -> sessionmaker:
    return sessionmaker(bind=get_engine(), autoflush=False, autocommit=False, future=True)

"""Database engine/session factory. No connection is opened at import time."""
from __future__ import annotations
import os
from functools import lru_cache
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker, Session

@lru_cache(maxsize=4)
def get_engine(url: str | None = None) -> Engine:
    database_url = url or os.getenv("CRI_DATABASE_URL", "")
    if not database_url:
        raise RuntimeError("CRI_DATABASE_URL is required for PostgreSQL persistence")
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql+psycopg://", 1)
    if database_url.startswith("postgresql://"):
        database_url = database_url.replace("postgresql://", "postgresql+psycopg://", 1)
    return create_engine(database_url, pool_pre_ping=True, pool_size=5, max_overflow=5)

def session_factory(engine: Engine | None = None):
    return sessionmaker(bind=engine or get_engine(), autoflush=False, expire_on_commit=False, class_=Session)

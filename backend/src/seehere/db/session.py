"""Engine and session management."""

from __future__ import annotations

from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from seehere.core.config import get_settings


@lru_cache
def get_engine(database_url: str | None = None) -> Engine:
    url = database_url or get_settings().database_url
    return create_engine(url, pool_pre_ping=True, connect_args={"connect_timeout": 5})


@lru_cache
def get_sessionmaker(database_url: str | None = None) -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(database_url), expire_on_commit=False)


def get_db() -> Iterator[Session]:
    """FastAPI dependency: one session per request, rolled back on error."""
    session = get_sessionmaker()()
    try:
        yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

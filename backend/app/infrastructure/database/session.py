"""
DocuFlow AI — Async Database Session Factory.

Creates the SQLAlchemy async engine and session factory.
Workers use NullPool to avoid connection leaks across Celery forked processes.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.config import Settings


def build_engine(settings: Settings, use_null_pool: bool = False):
    """Build the SQLAlchemy async engine.

    Args:
        settings: Application settings instance.
        use_null_pool: If True, use NullPool (for Celery workers).
    """
    kwargs = {
        "echo": settings.is_development,
        "future": True,
    }

    if use_null_pool:
        kwargs["poolclass"] = NullPool
    else:
        kwargs["pool_size"] = settings.db_pool_size
        kwargs["max_overflow"] = settings.db_max_overflow
        kwargs["pool_timeout"] = settings.db_pool_timeout
        kwargs["pool_recycle"] = settings.db_pool_recycle
        kwargs["pool_pre_ping"] = True

    return create_async_engine(settings.database_url, **kwargs)


def build_session_factory(engine) -> async_sessionmaker[AsyncSession]:
    """Build the session factory from an async engine."""
    return async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        autocommit=False,
        autoflush=False,
        expire_on_commit=False,
    )


@asynccontextmanager
async def get_db_session(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncGenerator[AsyncSession, None]:
    """Context manager yielding a database session.

    Handles commit on success and rollback on exception.

    Args:
        session_factory: The configured async_sessionmaker.
    """
    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

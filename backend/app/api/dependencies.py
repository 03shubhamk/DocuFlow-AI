"""
DocuFlow AI — FastAPI Dependency Injection Providers.

Provides reusable Depends() factories for:
- Database sessions
- Settings
- Authenticated user contexts (Phase 3+)
"""

from __future__ import annotations

from typing import Annotated, AsyncGenerator

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.infrastructure.database.session import build_engine, build_session_factory


def get_settings_dep() -> Settings:
    """Dependency: return validated application settings."""
    return get_settings()


SettingsDep = Annotated[Settings, Depends(get_settings_dep)]


async def get_db(settings: SettingsDep) -> AsyncGenerator[AsyncSession, None]:
    """Dependency: yield an async database session per request."""
    engine = build_engine(settings)
    session_factory = build_session_factory(engine)
    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


DbSession = Annotated[AsyncSession, Depends(get_db)]
